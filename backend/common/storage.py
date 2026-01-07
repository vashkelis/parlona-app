from __future__ import annotations

from pathlib import Path

from backend.common.config import get_settings


def ensure_storage_root() -> Path:
    root = Path(get_settings().storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_job_storage_dir(job_id: str) -> Path:
    job_dir = ensure_storage_root() / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir
