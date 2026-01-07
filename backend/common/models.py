from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, enum.Enum):
    queued = "queued"
    stt_in_progress = "stt_in_progress"
    stt_done = "stt_done"
    stt_failed = "stt_failed"
    summary_in_progress = "summary_in_progress"
    summary_done = "summary_done"
    postprocess_in_progress = "postprocess_in_progress"
    done = "done"
    failed = "failed"


class JobMetadata(BaseModel):
    job_id: str
    audio_path: str
    status: JobStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    dummy_transcript: Optional[str] = None
    dummy_summary: Optional[str] = None
    dummy_headline: Optional[str] = None
    dummy_tags: Optional[list[str]] = None
    delivered: bool = False
    notes: Optional[str] = None
    extra_meta: Optional[dict[str, Any]] = None
    stt_text: Optional[str] = None
    stt_language: Optional[str] = None
    stt_segments: Optional[list[dict[str, Any]]] = None
    stt_diarization_mode: Optional[str] = None
    stt_engine: Optional[str] = None
    stt_metadata: Optional[dict[str, Any]] = None
    stt_error: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    entities: Optional[dict[str, Any]] = None  # Supports both flat format and speaker-separated format


class QueueMessage(BaseModel):
    job_id: str
    audio_path: Optional[str] = None


class JobCreateRequest(BaseModel):
    audio_path: str
    extra_meta: Optional[dict[str, Any]] = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    audio_path: str


class JobDetailResponse(JobMetadata):
    pass


class JobListResponse(BaseModel):
    jobs: list[JobMetadata]