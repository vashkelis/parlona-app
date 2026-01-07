from __future__ import annotations

import hashlib
import json
import logging
import signal
import time
from datetime import datetime
from typing import Optional

from backend.common.config import Settings, get_settings
from backend.common.constants import QUEUE_POSTPROCESS_JOBS
from backend.common.db import db_settings
from backend.common.logging_utils import configure_logging
from backend.common.models import JobStatus, JobMetadata, QueueMessage
from backend.common.phone_utils import normalize_phone_e164, normalize_email
from backend.common.models_db import (
    Call,
    DialogueTurn,
    CallSummary,
    Agent,
    Person,
    Organization,
    Identifier,
    Extraction,
    ExtractedFact,
    Task,
    Offer,
    CallProductMention,
)
from backend.common.redis_utils import pop_message, update_job, get_job
from backend.common.db import get_session, engine, Base
from backend.postprocess_service.app.identity_resolver import (
    resolve_or_create_agent,
    resolve_or_create_person_org,
)

logger = logging.getLogger("postprocess_worker")


class PostprocessWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stopping = False
        configure_logging(service_name="postprocess_service")
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        # Run database migrations if configured
        if db_settings.run_db_migrations:
            logger.info("Skipping database migrations for debugging")
            # self._run_migrations()
        
        logger.info("Postprocess worker initialized and waiting for jobs")

    def _handle_shutdown(self, signum: int, frame: Optional[object]) -> None:  # noqa: ARG002
        logger.info("Received shutdown signal %s", signum)
        self._stopping = True

    def _run_migrations(self) -> None:
        """Run database migrations on startup if configured."""
        try:
            from alembic.config import Config
            from alembic import command
            import os
            
            # The working directory is /app, so alembic.ini is at /app/backend/alembic.ini
            alembic_ini_path = "/app/backend/alembic.ini"
            
            logger.info("Running database migrations...")
            alembic_cfg = Config(alembic_ini_path)
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.error("Failed to run database migrations: %s", e)

    def run(self) -> None:
        logger.info("Postprocess worker starting to poll for jobs")
        while not self._stopping:
            logger.debug("Polling for messages from queue: %s", QUEUE_POSTPROCESS_JOBS)
            message = pop_message(QUEUE_POSTPROCESS_JOBS, timeout=self.settings.queue_poll_timeout)
            if message is None:
                logger.debug("No message received from queue")
                continue
            logger.info("Received message from queue: %s", message.job_id)
            self._process_message(message)

    def _process_message(self, message: QueueMessage) -> None:
        job_id = message.job_id
        logger.info("Processing postprocess job %s", job_id)
        update_job(job_id, status=JobStatus.postprocess_in_progress)
        
        try:
            # Get the complete job data from Redis
            job_data = get_job(job_id)
            if not job_data:
                logger.error("Job %s not found in Redis", job_id)
                update_job(job_id, status=JobStatus.failed)
                return
            
            # Persist job data to PostgreSQL
            self._persist_to_database(job_data)
            
            logger.info("Simulated sending job %s payload to external system", job_id)
            update_job(job_id, status=JobStatus.done, delivered=True)
            logger.info("Postprocess job %s completed", job_id)
        except Exception as e:
            logger.error("Failed to process job %s: %s", job_id, e, exc_info=True)
            update_job(job_id, status=JobStatus.failed)

    def _map_channel_to_speaker(self, channel: int) -> str:
        """Map stereo channel to speaker role based on STT configuration."""
        # Default mapping - can be made configurable if needed
        if channel == 0:
            return "agent"
        elif channel == 1:
            return "customer"
        else:
            return "unknown"

    def _calculate_duration_sec(self, job: JobMetadata, call_record: Call) -> Optional[int]:
        """Calculate duration in seconds from job data."""
        # Try to calculate from started_at and ended_at if available
        if call_record.started_at and call_record.ended_at:
            duration = call_record.ended_at - call_record.started_at
            return int(duration.total_seconds())
        
        # Fallback to max dialogue turn end time
        if job.stt_segments:
            max_end_time = 0
            for segment in job.stt_segments:
                end_time = segment.get("end", 0)
                if end_time > max_end_time:
                    max_end_time = end_time
            return int(max_end_time) if max_end_time > 0 else None
        
        return None

    def _stable_key(self, call_id: int, fact_type: str, value: dict, label: Optional[str] = None) -> str:
        """
        Compute a deterministic stable key for a fact/business object.
        This is used to make postprocess idempotent on reruns.
        """
        payload = {
            "call_id": call_id,
            "fact_type": fact_type,
            "label": label,
            "value": value,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"{fact_type}:{digest}"

    def _normalize_phone(self, raw: str) -> Optional[str]:
        """Normalize phone number to E.164 format."""
        return normalize_phone_e164(raw, default_country="US")

    def _normalize_email(self, raw: str) -> Optional[str]:
        """Normalize email for identifier matching."""
        return normalize_email(raw)

    def _persist_to_database(self, job: JobMetadata) -> None:
        """Persist job data to PostgreSQL database with identity resolution and entity promotion."""
        try:
            import asyncio
            
            # Run the async database operation in a synchronous context
            async def _async_persist():
                # Import inside to create fresh engine in this thread's event loop
                from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
                from backend.common.db import db_settings
                from sqlalchemy import select, delete
                
                # Create a fresh engine for this thread to avoid loop conflicts
                local_engine = create_async_engine(
                    db_settings.postgres_dsn,
                    echo=False,
                    pool_pre_ping=True,
                )
                
                LocalSession = async_sessionmaker(
                    bind=local_engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )
                
                session = LocalSession()
                try:
                    # Check if call already exists
                    result = await session.execute(
                        select(Call).where(Call.external_job_id == job.job_id)
                    )
                    existing_call = result.scalar_one_or_none()
                    
                    # Extract metadata
                    agent_id_raw = None
                    customer_number = None
                    direction = None
                    provider_call_id = None
                    
                    if job.extra_meta:
                        agent_id_raw = job.extra_meta.get("agent_id")
                        customer_number = job.extra_meta.get("customer_number")
                        direction = job.extra_meta.get("direction")
                        provider_call_id = job.extra_meta.get("call_id")
                    
                    # Create or update call record
                    if existing_call:
                        existing_call.agent_id = agent_id_raw
                        existing_call.customer_number = customer_number
                        existing_call.direction = direction
                        existing_call.provider_call_id = provider_call_id
                        existing_call.audio_path = job.audio_path
                        existing_call.language = job.stt_language
                        existing_call.stt_model = job.stt_engine
                        existing_call.status = "completed"
                        call_record = existing_call
                    else:
                        call_record = Call(
                            external_job_id=job.job_id,
                            agent_id=agent_id_raw,
                            customer_number=customer_number,
                            direction=direction,
                            provider_call_id=provider_call_id,
                            audio_path=job.audio_path,
                            language=job.stt_language,
                            stt_model=job.stt_engine,
                            status="completed",
                        )
                        session.add(call_record)
                    
                    await session.flush()

                    # -------- Identity resolution (agent + person/org via identifiers) --------
                    # 1) Agent
                    if agent_id_raw:
                        agent = await resolve_or_create_agent(session, agent_id_raw)
                        if agent:
                            call_record.agent_fk = agent.id

                    # 2) Person / organization via identifiers (phone/email)
                    entities = job.entities or {}
                    if not isinstance(entities, dict):
                        entities = {}

                    identity_hints = entities.get("identity_hints") or {}
                    phones: list[str] = []
                    emails: list[str] = []
                    person_names: list[str] = []
                    company_names: list[str] = []

                    if customer_number:
                        phones.append(customer_number)
                    if isinstance(identity_hints, dict):
                        phones.extend(identity_hints.get("phones") or [])
                        emails.extend(identity_hints.get("emails") or [])
                        person_names = identity_hints.get("person_names") or []
                        company_names = identity_hints.get("company_names") or []

                    normalized_phones = [
                        self._normalize_phone(p) for p in phones if self._normalize_phone(p)
                    ]
                    normalized_emails = [
                        self._normalize_email(e) for e in emails if self._normalize_email(e)
                    ]

                    person, organization = await resolve_or_create_person_org(
                        session,
                        normalized_phones,
                        normalized_emails,
                        person_names,
                        company_names,
                    )

                    if person:
                        call_record.person_id = person.id
                    if organization:
                        call_record.organization_id = organization.id

                    await session.flush()

                    # -------- Existing pipeline: dialogue turns & call summaries --------
                    
                    # Clear existing dialogue turns for this call (if any)
                    await session.execute(
                        delete(DialogueTurn).where(DialogueTurn.call_id == call_record.id)
                    )
                    
                    # Build turn_index -> turn_id mapping for extracted facts
                    turn_id_map = {}
                    if job.stt_segments:
                        for idx, segment_data in enumerate(job.stt_segments):
                            speaker = segment_data.get("speaker", "unknown")
                            channel = segment_data.get("channel")
                            if channel is not None:
                                speaker = self._map_channel_to_speaker(channel)
                            
                            dialogue_turn = DialogueTurn(
                                call_id=call_record.id,
                                turn_index=idx,
                                speaker=speaker,
                                channel=channel,
                                start_sec=segment_data.get("start"),
                                end_sec=segment_data.get("end"),
                                text=segment_data.get("text", ""),
                                raw_json=segment_data,
                            )
                            session.add(dialogue_turn)
                            await session.flush()
                            turn_id_map[idx] = dialogue_turn.id
                    
                    # Clear existing summaries for this call (if any)
                    await session.execute(
                        delete(CallSummary).where(CallSummary.call_id == call_record.id)
                    )
                    
                    # Add summaries if available and populate materialized fields
                    if job.dummy_summary:
                        summary_payload = {
                            "text": job.dummy_summary,
                            "headline": job.dummy_headline or "",
                            "tags": job.dummy_tags or [],
                            "sentiment_label": job.sentiment_label or "neutral",
                            "sentiment_score": job.sentiment_score or 0.0,
                            "entities": job.entities or {},
                        }
                        call_summary = CallSummary(
                            call_id=call_record.id,
                            summary_type="llm_generated",
                            payload=summary_payload,
                            model="openai_gpt",
                        )
                        session.add(call_summary)
                        
                        # Materialize dashboard fields
                        if summary_payload.get("headline"):
                            call_record.headline = summary_payload["headline"]
                        call_record.sentiment_label = summary_payload.get("sentiment_label")
                        call_record.sentiment_score = summary_payload.get("sentiment_score")
                        call_record.duration_sec = self._calculate_duration_sec(job, call_record)
                        
                        # Store snapshot-style entities for backward compatibility
                        call_record.entities = job.entities

                        # -------- New: provenance-first extraction + facts + tasks/offers --------
                        extraction = Extraction(
                            call_id=call_record.id,
                            extractor_name="summary_service",
                            extractor_version="v1",
                            run_type="llm_summary",
                            status="succeeded",
                            raw_payload={
                                "summary": summary_payload,
                                "language": job.stt_language,
                                "entities": job.entities or {},
                            },
                        )
                        session.add(extraction)
                        await session.flush()

                        entities_struct = job.entities or {}
                        if not isinstance(entities_struct, dict):
                            entities_struct = {}

                        # Process tasks
                        task_items = entities_struct.get("tasks") or []
                        for task_data in task_items:
                            if not isinstance(task_data, dict):
                                continue

                            stable_key = self._stable_key(
                                call_id=call_record.id,
                                fact_type="task",
                                value=task_data,
                            )

                            # Create extracted fact
                            turn_index = task_data.get("turn_index")
                            turn_id = turn_id_map.get(turn_index) if turn_index is not None else None
                            
                            fact = ExtractedFact(
                                extraction_id=extraction.id,
                                call_id=call_record.id,
                                fact_type="task",
                                label=None,
                                value=task_data,
                                status="proposed",
                                confidence=task_data.get("confidence", 0.8),
                                turn_id=turn_id,
                                start_sec=task_data.get("start_sec"),
                                end_sec=task_data.get("end_sec"),
                                raw_span_text=task_data.get("text"),
                                stable_key=stable_key,
                            )
                            session.add(fact)
                            await session.flush()

                            # Upsert task (idempotent via stable_key)
                            task_result = await session.execute(
                                select(Task).where(
                                    Task.call_id == call_record.id,
                                    Task.stable_key == stable_key,
                                )
                            )
                            existing_task = task_result.scalar_one_or_none()

                            title = task_data.get("title", "Untitled task")
                            description = task_data.get("description")
                            owner_info = task_data.get("owner") or {}
                            owner_agent_id = None
                            if isinstance(owner_info, dict) and owner_info.get("role") == "agent":
                                # Try to resolve agent by external_agent_id if provided
                                if agent and owner_info.get("agent_id") == agent_id_raw:
                                    owner_agent_id = agent.id

                            if existing_task:
                                # Update if needed
                                existing_task.title = title
                                existing_task.description = description
                                existing_task.owner_agent_id = owner_agent_id
                                existing_task.person_id = person.id if person else None
                                existing_task.organization_id = organization.id if organization else None
                                existing_task.fact_id = fact.id
                                task_obj = existing_task
                            else:
                                task_obj = Task(
                                    call_id=call_record.id,
                                    extraction_id=extraction.id,
                                    fact_id=fact.id,
                                    title=title,
                                    description=description,
                                    status="open",
                                    owner_agent_id=owner_agent_id,
                                    person_id=person.id if person else None,
                                    organization_id=organization.id if organization else None,
                                    stable_key=stable_key,
                                )
                                session.add(task_obj)
                            await session.flush()
                            # Link fact back to task
                            fact.task_id = task_obj.id

                        # Process offers
                        offer_items = entities_struct.get("offers") or []
                        for offer_data in offer_items:
                            if not isinstance(offer_data, dict):
                                continue

                            stable_key = self._stable_key(
                                call_id=call_record.id,
                                fact_type="offer",
                                value=offer_data,
                            )

                            turn_index = offer_data.get("turn_index")
                            turn_id = turn_id_map.get(turn_index) if turn_index is not None else None

                            fact = ExtractedFact(
                                extraction_id=extraction.id,
                                call_id=call_record.id,
                                fact_type="offer",
                                label=None,
                                value=offer_data,
                                status="proposed",
                                confidence=offer_data.get("confidence", 0.8),
                                turn_id=turn_id,
                                start_sec=offer_data.get("start_sec"),
                                end_sec=offer_data.get("end_sec"),
                                stable_key=stable_key,
                            )
                            session.add(fact)
                            await session.flush()

                            # Upsert offer
                            offer_result = await session.execute(
                                select(Offer).where(
                                    Offer.call_id == call_record.id,
                                    Offer.stable_key == stable_key,
                                )
                            )
                            existing_offer = offer_result.scalar_one_or_none()

                            description = offer_data.get("description", "Untitled offer")
                            discount_info = offer_data.get("discount") or {}

                            if existing_offer:
                                existing_offer.description = description
                                existing_offer.discount_amount = discount_info.get("amount")
                                existing_offer.discount_percent = discount_info.get("percent")
                                existing_offer.person_id = person.id if person else None
                                existing_offer.organization_id = organization.id if organization else None
                                existing_offer.fact_id = fact.id
                                offer_obj = existing_offer
                            else:
                                offer_obj = Offer(
                                    call_id=call_record.id,
                                    extraction_id=extraction.id,
                                    fact_id=fact.id,
                                    description=description,
                                    status=offer_data.get("status", "promised"),
                                    discount_amount=discount_info.get("amount"),
                                    discount_percent=discount_info.get("percent"),
                                    person_id=person.id if person else None,
                                    organization_id=organization.id if organization else None,
                                    stable_key=stable_key,
                                )
                                session.add(offer_obj)
                            await session.flush()
                            fact.offer_id = offer_obj.id

                        # Process product mentions
                        product_items = entities_struct.get("products") or []
                        for product_data in product_items:
                            if not isinstance(product_data, dict):
                                continue

                            stable_key = self._stable_key(
                                call_id=call_record.id,
                                fact_type="product_mention",
                                value=product_data,
                            )

                            turn_index = product_data.get("turn_index")
                            turn_id = turn_id_map.get(turn_index) if turn_index is not None else None

                            fact = ExtractedFact(
                                extraction_id=extraction.id,
                                call_id=call_record.id,
                                fact_type="product_mention",
                                label=None,
                                value=product_data,
                                status="proposed",
                                confidence=product_data.get("confidence", 0.8),
                                turn_id=turn_id,
                                start_sec=product_data.get("start_sec"),
                                end_sec=product_data.get("end_sec"),
                                stable_key=stable_key,
                            )
                            session.add(fact)
                            await session.flush()

                            # Upsert product mention
                            mention_result = await session.execute(
                                select(CallProductMention).where(
                                    CallProductMention.call_id == call_record.id,
                                    CallProductMention.stable_key == stable_key,
                                )
                            )
                            existing_mention = mention_result.scalar_one_or_none()

                            mentioned_name = product_data.get("name", "Unknown product")
                            price_info = product_data.get("price") or {}

                            if existing_mention:
                                existing_mention.mentioned_name = mentioned_name
                                existing_mention.quantity = product_data.get("quantity")
                                existing_mention.quantity_unit = product_data.get("unit")
                                existing_mention.price_amount = price_info.get("amount")
                                existing_mention.price_currency = price_info.get("currency")
                                existing_mention.context = product_data.get("context")
                                existing_mention.person_id = person.id if person else None
                                existing_mention.organization_id = organization.id if organization else None
                                existing_mention.fact_id = fact.id
                                mention_obj = existing_mention
                            else:
                                mention_obj = CallProductMention(
                                    call_id=call_record.id,
                                    extraction_id=extraction.id,
                                    fact_id=fact.id,
                                    mentioned_name=mentioned_name,
                                    quantity=product_data.get("quantity"),
                                    quantity_unit=product_data.get("unit"),
                                    price_amount=price_info.get("amount"),
                                    price_currency=price_info.get("currency"),
                                    context=product_data.get("context"),
                                    start_sec=product_data.get("start_sec"),
                                    end_sec=product_data.get("end_sec"),
                                    person_id=person.id if person else None,
                                    organization_id=organization.id if organization else None,
                                    stable_key=stable_key,
                                )
                                session.add(mention_obj)
                            await session.flush()
                            fact.product_id = mention_obj.id
                    
                    await session.commit()
                    logger.info("Successfully persisted job %s to database with identity resolution", job.job_id)
                finally:
                    await session.close()
                    await local_engine.dispose()  # Close the engine connections
            
            # Run the async function in a separate thread with its own event loop
            import concurrent.futures
            import threading
            
            result_container = []
            error_container = []
            
            def run_in_thread():
                try:
                    # Create a new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(_async_persist())
                        result_container.append(True)
                    finally:
                        loop.close()
                except Exception as e:
                    error_container.append(e)
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join(timeout=30)  # Wait max 30 seconds
            
            if thread.is_alive():
                raise TimeoutError("Database persistence took too long")
            
            if error_container:
                raise error_container[0]
            
        except Exception as e:
            logger.error("Failed to persist job %s to database: %s", job.job_id, e, exc_info=True)
            raise


def start_worker() -> None:
    worker = PostprocessWorker(get_settings())
    worker.run()