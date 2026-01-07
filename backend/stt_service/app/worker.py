from __future__ import annotations

import logging
import signal
import traceback
from pathlib import Path
from typing import Optional

from backend.common.config import Settings, get_settings
from backend.common.constants import QUEUE_STT_JOBS
from backend.common.logging_utils import configure_logging
from backend.common.models import JobStatus, QueueMessage
from backend.common.redis_utils import enqueue_summary_job, get_job, pop_message, update_job
from backend.stt_service.app.config import STTServiceSettings, get_stt_settings
from backend.stt_service.app.stt_engine import BaseSTTEngine, FasterWhisperEngine

logger = logging.getLogger("stt_worker")


class STTWorker:
    def __init__(self, settings: Settings, stt_settings: STTServiceSettings) -> None:
        self.settings = settings
        self.stt_settings = stt_settings
        self._stopping = False
        configure_logging(service_name="stt_service")
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        self.engine = self._load_engine()
        logger.info(
            "STT worker initialized (engine=%s, diarization=%s)",
            self.engine.name,
            stt_settings.diarization_mode,
        )

    def _load_engine(self) -> BaseSTTEngine:
        engine_name = self.stt_settings.stt_engine.lower()
        if engine_name == "faster_whisper":
            return FasterWhisperEngine(self.stt_settings)
        raise ValueError(f"Unsupported STT engine: {engine_name}")

    def _handle_shutdown(self, signum: int, frame: Optional[object]) -> None:  # noqa: ARG002
        logger.info("Received shutdown signal %s", signum)
        self._stopping = True

    def run(self) -> None:
        while not self._stopping:
            message = pop_message(QUEUE_STT_JOBS, timeout=self.settings.queue_poll_timeout)
            if message is None:
                continue
            self._process_message(message)

    def _process_message(self, message: QueueMessage) -> None:
        job_id = message.job_id
        job = get_job(job_id)
        if not job:
            logger.warning("Received STT message for unknown job %s", job_id)
            return

        try:
            audio_path = self._resolve_audio_path(job.audio_path)
        except FileNotFoundError as exc:
            logger.error("STT job %s missing audio: %s", job_id, exc)
            update_job(
                job_id,
                status=JobStatus.stt_failed,
                stt_error=str(exc),
            )
            return
        logger.info("Processing STT job %s (audio=%s)", job_id, audio_path)
        update_job(job_id, status=JobStatus.stt_in_progress)

        try:
            result = self.engine.transcribe(
                job_id=job_id,
                audio_path=audio_path,
                diarization_mode=self.stt_settings.diarization_mode,
                extra_meta=job.extra_meta if job else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("STT job %s failed: %s", job_id, exc)
            logger.debug(traceback.format_exc())
            update_job(
                job_id,
                status=JobStatus.stt_failed,
                stt_error=str(exc),
            )
            return

        update_job(
            job_id,
            status=JobStatus.stt_done,
            stt_text=result.text,
            stt_language=result.language,
            stt_segments=result.segments_as_dicts(),
            stt_diarization_mode=self.stt_settings.diarization_mode,
            stt_engine=self.engine.name,
            stt_metadata=result.metadata,
        )
        enqueue_summary_job(QueueMessage(job_id=job_id))
        logger.info("STT job %s completed and forwarded", job_id)

    def _resolve_audio_path(self, original_path: str) -> str:
        original = Path(original_path)
        candidates = [original]

        for host_prefix, container_prefix in self.stt_settings.path_mappings:
            if original_path.startswith(host_prefix):
                relative = original_path[len(host_prefix):].lstrip("/")
                mapped = Path(container_prefix) / relative
                candidates.insert(0, mapped)
                break

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        mapping_hint = (
            " Configure STT_AUDIO_PATH_MAPPINGS or mount the host directory into the container."
            if self.stt_settings.path_mappings
            else " Ensure the audio directory is mounted into the stt_service container."
        )
        raise FileNotFoundError(f"Audio path '{original_path}' not found inside container.{mapping_hint}")


def start_worker() -> None:
    worker = STTWorker(get_settings(), get_stt_settings())
    worker.run()
