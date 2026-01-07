from __future__ import annotations

from typing import Any, Optional, List

from pydantic import BaseModel

from backend.common.models import JobMetadata, JobStatus


class JobCreatePayload(BaseModel):
    audio_path: str
    extra_meta: Optional[dict[str, Any]] = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    audio_path: str


class JobDetail(JobMetadata):
    pass


class JobList(BaseModel):
    jobs: list[JobMetadata]


# Transcript bypass schemas
class TranscriptParticipant(BaseModel):
    """Participant in the dialogue."""
    role: str  # "agent" or "customer"
    id: str
    name: Optional[str] = None


class TranscriptTurn(BaseModel):
    """Single dialogue turn."""
    speaker_role: str
    speaker_id: str
    start_offset_ms: int
    end_offset_ms: int
    text: str


class TranscriptMetadata(BaseModel):
    """Call metadata."""
    date: str
    start_time: str
    duration_seconds: int
    recording_enabled: bool = True
    language: str = "ru-RU"


class TranscriptInput(BaseModel):
    """Complete transcript input for bypassing STT."""
    call_id: str
    direction: str  # "inbound" or "outbound"
    agent_id: str
    customer_number: str
    metadata: TranscriptMetadata
    participants: List[TranscriptParticipant]
    transcript: List[TranscriptTurn]


class TranscriptJobResponse(BaseModel):
    """Response for transcript submission."""
    job_id: str
    status: str
    call_id: str
