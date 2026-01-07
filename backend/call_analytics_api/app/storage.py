from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import UploadFile

from backend.common.config import get_settings


def save_upload_file(upload_file: UploadFile, job_id: str) -> str:
    settings = get_settings()
    storage_root = Path(settings.storage_dir)
    storage_root.mkdir(parents=True, exist_ok=True)
    job_dir = storage_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(upload_file.filename or "audio.wav").name
    destination = job_dir / filename

    upload_file.file.seek(0)
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return str(destination)
