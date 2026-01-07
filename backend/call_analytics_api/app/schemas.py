from __future__ import annotations

from typing import Any, Optional

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
