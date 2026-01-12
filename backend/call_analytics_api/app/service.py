from __future__ import annotations

from uuid import uuid4

from fastapi import UploadFile

from backend.call_analytics_api.app.storage import save_upload_file
from backend.common.config import get_settings
from backend.common.models import JobMetadata, JobStatus, QueueMessage
from backend.common.redis_utils import create_job, enqueue_stt_job, enqueue_summary_job, get_job, list_jobs
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


def create_transcript_job(transcript_input) -> JobMetadata:
    """Create a job from pre-transcribed dialogue, bypassing STT."""
    # Convert transcript to STT-like format
    stt_segments = []
    full_text = ""
    
    for i, turn in enumerate(transcript_input.transcript):
        start_sec = turn.start_offset_ms / 1000.0
        end_sec = turn.end_offset_ms / 1000.0
        
        stt_segments.append({
            "start": start_sec,
            "end": end_sec,
            "text": turn.text,
            "speaker": turn.speaker_role
        })
        
        if full_text:
            full_text += " "
        full_text += turn.text
    
    # Extract duration from metadata if available
    duration_seconds = getattr(transcript_input.metadata, 'duration_seconds', None)
    
    # Create job metadata indicating bypassed STT
    extra_meta = {
        "call_id": transcript_input.call_id,
        "direction": transcript_input.direction,
        "agent_id": transcript_input.agent_id,
        "customer_number": transcript_input.customer_number,
        "participants": [p.dict() for p in transcript_input.participants],
        "bypass_stt": True,
        "source": "transcript_api"
    }
    
    # Add duration if provided
    if duration_seconds is not None:
        extra_meta["duration_seconds"] = duration_seconds
    
    job = JobMetadata(
        job_id=str(uuid4()),
        audio_path="",  # No audio file since we're bypassing STT
        status=JobStatus.stt_done,  # Skip STT phase
        stt_text=full_text,
        stt_segments=stt_segments,
        stt_language=transcript_input.metadata.language,
        extra_meta=extra_meta
    )
    
    # Save job to Redis
    create_job(job)
    
    # Push directly to summary queue (bypass STT queue)
    enqueue_summary_job(QueueMessage(job_id=job.job_id))
    
    return job
