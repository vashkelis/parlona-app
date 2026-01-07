from __future__ import annotations

import logging
import asyncio

from fastapi import FastAPI

from backend.call_analytics_api.app.api import router as jobs_router
from backend.common.db import db_settings
from backend.common.logging_utils import configure_logging
from backend.common.config import get_settings

configure_logging(service_name="call_analytics_api")
logger = logging.getLogger("call_analytics_api")

# Initialize settings to validate configuration early
try:
    settings = get_settings()
    logger.info("API server configured with CALL_API_KEY (length: %d)", len(settings.call_api_key))
except Exception as e:
    logger.error("Failed to initialize settings: %s", e)
    raise

app = FastAPI(title="Call Analytics Orchestrator API", version="0.1.0")
app.include_router(jobs_router)


@app.on_event("startup")
async def startup_event():
    """Run database migrations on startup if configured."""
    if db_settings.run_db_migrations:
        try:
            from alembic.config import Config
            from alembic import command
            import os
            
            # The working directory is /app, so alembic.ini is at /app/backend/alembic.ini
            alembic_ini_path = "/app/backend/alembic.ini"
            
            logger.info("Running database migrations...")
            alembic_cfg = Config(alembic_ini_path)
            
            # Run the upgrade command in a separate thread to avoid blocking
            # the async event loop
            def run_upgrade():
                command.upgrade(alembic_cfg, "head")
                
            # Execute the sync function in a thread pool
            import concurrent.futures
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, run_upgrade)
                
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.error("Failed to run database migrations: %s", e, exc_info=True)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/v1/health")
def v1_health_check():
    return {"status": "healthy"}