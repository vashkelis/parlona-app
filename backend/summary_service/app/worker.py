from __future__ import annotations

import logging
import signal
import time
from typing import Optional

from backend.common.config import Settings, get_settings
from backend.common.constants import QUEUE_SUMMARY_JOBS
from backend.common.models import JobStatus, QueueMessage
from backend.common.redis_utils import (
    enqueue_postprocess_job,
    get_job,
    pop_message,
    update_job,
)
from backend.common.logging_utils import configure_logging
from backend.common.llm_utils import get_llm_client

logger = logging.getLogger("summary_worker")


class SummaryWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stopping = False
        self.llm_client = get_llm_client(settings)
        configure_logging(service_name="summary_service")
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        logger.info("Summary worker initialized and waiting for jobs")

    def _handle_shutdown(self, signum: int, frame: Optional[object]) -> None:  # noqa: ARG002
        logger.info("Received shutdown signal %s", signum)
        self._stopping = True

    def run(self) -> None:
        while not self._stopping:
            message = pop_message(QUEUE_SUMMARY_JOBS, timeout=self.settings.queue_poll_timeout)
            if message is None:
                continue
            self._process_message(message)

    def _process_message(self, message: QueueMessage) -> None:
        job_id = message.job_id
        logger.info("Processing summary job %s", job_id)
        
        try:
            update_job(job_id, status=JobStatus.summary_in_progress)
            job = get_job(job_id)
            transcript = None
            if job:
                transcript = job.stt_text or job.dummy_transcript
            
            if not transcript:
                logger.warning("No transcript found for job %s", job_id)
                summary = "No transcript available for summarization"
                headline = "No transcript available"
                language = "unknown"
                sentiment_label = "neutral"
                sentiment_score = 0.5
                entities = {}
            else:
                logger.info("Generating summary, headline, sentiment, and entities for job %s transcript (length: %d chars)", job_id, len(transcript))
                # Generate summary, headline, sentiment, and entities using LLM
                summary, headline, language, sentiment_label, entities, sentiment_score = self.llm_client.summarize_with_headline(transcript, max_sentences=4)
                logger.info("Generated summary for job %s in language %s: %s", job_id, language, summary)
                logger.info("Generated headline for job %s in language %s: %s", job_id, language, headline)
                logger.info("Generated sentiment for job %s: %s (%.2f)", job_id, sentiment_label, sentiment_score)
                logger.info("Extracted entities for job %s: %s", job_id, entities)
            
            tags = ["summary", "llm", language]
            update_job(
                job_id,
                status=JobStatus.summary_done,
                dummy_summary=summary,
                dummy_headline=headline,
                dummy_tags=tags,
                sentiment_label=sentiment_label,
                sentiment_score=sentiment_score,
                entities=entities
            )
            enqueue_postprocess_job(QueueMessage(job_id=job_id))
            logger.info("Summary job %s completed and forwarded", job_id)
            
        except Exception as exc:
            logger.error("Failed to process summary job %s: %s", job_id, exc, exc_info=True)
            update_job(job_id, status=JobStatus.failed, error=str(exc))


def start_worker() -> None:
    worker = SummaryWorker(get_settings())
    worker.run()