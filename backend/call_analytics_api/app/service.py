from __future__ import annotations

from uuid import uuid4

from fastapi import UploadFile

from backend.call_analytics_api.app.storage import save_upload_file
from backend.common.config import get_settings
from backend.common.models import JobMetadata, JobStatus, QueueMessage
from backend.common.redis_utils import create_job, enqueue_stt_job, get_job, list_jobs
from backend.stt_service.app.config import get_stt_settings


def create_job_entry(audio_path: str, extra_meta: dict | None = None) -> JobMetadata:
    job_id = str(uuid4())
    return _create_job(job_id=job_id, audio_path=audio_path, extra_meta=extra_meta)


async def create_job_from_upload(file: UploadFile, extra_meta: dict | None = None) -> JobMetadata:
    job_id = str(uuid4())
    stored_path = save_upload_file(file, job_id)
    return _create_job(job_id=job_id, audio_path=stored_path, extra_meta=extra_meta)


def _create_job(job_id: str, audio_path: str, extra_meta: dict | None = None) -> JobMetadata:
    # Get STT settings to include diarization mode in job metadata
    stt_settings = get_stt_settings()
    job_meta = {
        'stt_diarization_mode': stt_settings.diarization_mode,
        **(extra_meta or {})
    }
    
    job = JobMetadata(
        job_id=job_id,
        audio_path=audio_path,
        status=JobStatus.queued,
        extra_meta=job_meta,
        stt_diarization_mode=stt_settings.diarization_mode,
    )
    create_job(job)
    enqueue_stt_job(QueueMessage(job_id=job_id, audio_path=audio_path))
    return job


def fetch_job(job_id: str) -> JobMetadata | None:
    return get_job(job_id)


def fetch_jobs() -> list[JobMetadata]:
    settings = get_settings()
    return list_jobs(limit=settings.job_list_limit)
