from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Iterable

import redis

from backend.common.config import get_settings
from backend.common.constants import (
    JOB_KEY_PREFIX,
    JOB_LIST_KEY,
    QUEUE_POSTPROCESS_JOBS,
    QUEUE_STT_JOBS,
    QUEUE_SUMMARY_JOBS,
)
from backend.common.models import JobMetadata, JobStatus, QueueMessage

_settings = get_settings()
_redis_client: redis.Redis | None = None
_JSON_FIELDS = {"dummy_tags", "extra_meta", "stt_segments", "stt_metadata", "entities"}


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(_settings.redis_url, decode_responses=True)
    return _redis_client


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def enqueue_stt_job(message: QueueMessage) -> None:
    enqueue_message(QUEUE_STT_JOBS, message)


def enqueue_summary_job(message: QueueMessage) -> None:
    enqueue_message(QUEUE_SUMMARY_JOBS, message)


def enqueue_postprocess_job(message: QueueMessage) -> None:
    enqueue_message(QUEUE_POSTPROCESS_JOBS, message)


def enqueue_message(queue_name: str, message: QueueMessage) -> None:
    client = get_redis_client()
    client.rpush(queue_name, message.model_dump_json())


def pop_message(queue_name: str, timeout: int | None = None) -> QueueMessage | None:
    client = get_redis_client()
    result = client.blpop(queue_name, timeout=timeout)
    if result is None:
        return None
    _, message_str = result
    return QueueMessage.model_validate_json(message_str)


def create_job(job: JobMetadata) -> None:
    client = get_redis_client()
    job_hash = job_dict(job)
    client.hset(_job_key(job.job_id), mapping=job_hash)
    client.lpush(JOB_LIST_KEY, job.job_id)


def job_dict(job: JobMetadata) -> dict[str, Any]:
    data = job.model_dump()
    _encode_json_fields(data)
    return {k: _stringify(v) for k, v in data.items() if v is not None}


def update_job(job_id: str, **fields: Any) -> None:
    client = get_redis_client()
    fields["updated_at"] = datetime.utcnow().isoformat()
    _encode_json_fields(fields)
    client.hset(_job_key(job_id), mapping={k: _stringify(v) for k, v in fields.items()})


def get_job(job_id: str) -> JobMetadata | None:
    client = get_redis_client()
    job_hash = client.hgetall(_job_key(job_id))
    if not job_hash:
        return None
    job_hash = _deserialize_job_hash(job_hash)
    return JobMetadata(**job_hash)


def list_jobs(limit: int | None = None) -> list[JobMetadata]:
    client = get_redis_client()
    job_ids = client.lrange(JOB_LIST_KEY, 0, (limit or _settings.job_list_limit) - 1)
    jobs: list[JobMetadata] = []
    for job_id in job_ids:
        job = get_job(job_id)
        if job:
            jobs.append(job)
    return jobs


def _deserialize_job_hash(data: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in {"created_at", "updated_at"}:
            result[key] = datetime.fromisoformat(value)
        elif key == "status":
            result[key] = _deserialize_status(value)
        elif key in _JSON_FIELDS:
            result[key] = json.loads(value)
        elif key == "delivered":
            result[key] = value == "True"
        elif key in {"stt_language", "stt_text", "stt_engine", "stt_diarization_mode", "stt_error"}:
            # Handle special string fields that can be "None"
            result[key] = None if value == "None" else value
        else:
            result[key] = value
    return result


def _stringify(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _encode_json_fields(data: dict[str, Any]) -> None:
    for field in _JSON_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value is None:
            continue
        if isinstance(value, str):
            # already serialized
            continue
        if isinstance(value, Iterable) and not isinstance(value, (dict, list)) and field == "dummy_tags":
            value = list(value)
        data[field] = json.dumps(value)


def _deserialize_status(value: str) -> JobStatus:
    try:
        return JobStatus(value)
    except ValueError:
        if value.startswith("JobStatus."):
            stripped = value.split(".", 1)[1]
            return JobStatus(stripped)
        raise