from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi import File as FastAPIFile
from fastapi import Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.call_analytics_api.app import schemas, service
from backend.call_analytics_api.app.schemas_db import CallListItemOut, CallDetailsOut, CallListResponse
from backend.call_analytics_api.app.schemas_business import (
    PersonListItemOut,
    PersonDetailsOut,
    TaskListItemOut,
    TaskOut,
    TaskUpdateIn,
)
from backend.call_analytics_api.app.auth import verify_api_key  # Import the auth dependency
from backend.call_analytics_api.app.repos.calls import list_calls, get_call_details
from backend.call_analytics_api.app.repos.analytics import AnalyticsRepository
from backend.call_analytics_api.app.repos.customers import (
    list_customers,
    get_customer_details,
)
from backend.call_analytics_api.app.repos.tasks import (
    list_tasks,
    get_task_details,
    update_task,
    get_tasks_for_person,
)
from backend.call_analytics_api.app.repos.offers import get_offers_for_person
from backend.common.db import get_session
from backend.common.models_db import Call, DialogueTurn, CallSummary

# Create router with API key protection for all endpoints except health checks
router = APIRouter(prefix="/v1", tags=["jobs"], dependencies=[Depends(verify_api_key)])


@router.post("/jobs", response_model=schemas.JobResponse)
def create_job(payload: schemas.JobCreatePayload) -> schemas.JobResponse:
    job = service.create_job_entry(audio_path=payload.audio_path, extra_meta=payload.extra_meta)
    return schemas.JobResponse(job_id=job.job_id, status=job.status, audio_path=job.audio_path)


@router.post("/jobs/upload", response_model=schemas.JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job_from_upload(
    file: UploadFile = FastAPIFile(...),
    metadata: str | None = Form(default=None),
) -> schemas.JobResponse:
    extra_meta = None
    if metadata:
        extra_meta = json.loads(metadata)
    job = await service.create_job_from_upload(file=file, extra_meta=extra_meta)
    return schemas.JobResponse(job_id=job.job_id, status=job.status, audio_path=job.audio_path)


@router.get("/jobs/{job_id}", response_model=schemas.JobDetail)
def get_job(job_id: str) -> schemas.JobDetail:
    job = service.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return schemas.JobDetail(**job.model_dump())


@router.get("/jobs", response_model=schemas.JobList)
def list_jobs() -> schemas.JobList:
    jobs = service.fetch_jobs()
    return schemas.JobList(jobs=jobs)


@router.post("/jobs/transcript", response_model=schemas.TranscriptJobResponse, status_code=status.HTTP_201_CREATED)
def create_job_from_transcript(
    transcript_input: schemas.TranscriptInput
) -> schemas.TranscriptJobResponse:
    """
    Create a job from pre-transcribed dialogue, bypassing the STT service.
    
    This endpoint accepts structured dialogue data and pushes it directly 
    to the summarization pipeline, skipping speech-to-text processing.
    """
    job = service.create_transcript_job(transcript_input)
    return schemas.TranscriptJobResponse(
        job_id=job.job_id,
        status=str(job.status),
        call_id=transcript_input.call_id
    )


# New database endpoints
@router.get("/calls", response_model=CallListResponse)
async def list_calls_endpoint(
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    direction: str | None = Query(None, description="Filter by call direction"),
    limit: int = Query(50, le=100, description="Number of records to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_session)
):
    """List calls with optional filtering - optimized for dashboard queries."""
    return await list_calls(db, agent_id, direction, limit, offset)


@router.get("/calls/{call_id}", response_model=CallDetailsOut)
async def get_call_endpoint(
    call_id: int,
    db: AsyncSession = Depends(get_session)
):
    """Get detailed call information with dialogue turns and summaries."""
    call_details = await get_call_details(db, call_id)
    if not call_details:
        raise HTTPException(status_code=404, detail="Call not found")
    return call_details


# Customers endpoints
@router.get("/customers", response_model=list[PersonListItemOut])
async def list_customers_endpoint(
    query: str | None = Query(None, description="Search by name"),
    limit: int = Query(50, le=100, description="Number of records to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_session)
):
    """List customers/people with optional search."""
    return await list_customers(db, query, limit, offset)


@router.get("/customers/{person_id}", response_model=PersonDetailsOut)
async def get_customer_endpoint(
    person_id: int,
    db: AsyncSession = Depends(get_session)
):
    """Get detailed customer/person information."""
    customer = await get_customer_details(db, person_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/customers/{person_id}/tasks", response_model=list[TaskOut])
async def get_customer_tasks_endpoint(
    person_id: int,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session)
):
    """Get tasks for a specific customer."""
    return await get_tasks_for_person(db, person_id, limit, offset)


@router.get("/customers/{person_id}/offers", response_model=list)
async def get_customer_offers_endpoint(
    person_id: int,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session)
):
    """Get offers for a specific customer."""
    return await get_offers_for_person(db, person_id, limit, offset)


# Tasks endpoints
@router.get("/tasks", response_model=list[TaskListItemOut])
async def list_tasks_endpoint(
    status: str | None = Query(None, description="Filter by task status"),
    person_id: int | None = Query(None, description="Filter by customer ID"),
    owner_agent_id: int | None = Query(None, description="Filter by owner agent ID"),
    limit: int = Query(50, le=100, description="Number of records to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_session)
):
    """List tasks with optional filtering."""
    return await list_tasks(db, status, person_id, owner_agent_id, limit, offset)


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task_endpoint(
    task_id: int,
    db: AsyncSession = Depends(get_session)
):
    """Get detailed task information."""
    task = await get_task_details(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task_endpoint(
    task_id: int,
    update_data: TaskUpdateIn,
    db: AsyncSession = Depends(get_session)
):
    """Update task fields (status, due_at, owner, etc)."""
    task = await update_task(db, task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# Analytics endpoints
@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get complete analytics dashboard data."""
    # Get all analytics data in parallel
    kpi_metrics = await AnalyticsRepository.get_kpi_metrics(db, days_back)
    daily_volume = await AnalyticsRepository.get_daily_call_volume(db, days_back)
    hourly_dist = await AnalyticsRepository.get_hourly_call_distribution(db, days_back)
    sentiment_dist = await AnalyticsRepository.get_sentiment_distribution(db, days_back)
    call_categories = await AnalyticsRepository.get_call_categories(db, days_back)
    resolution_buckets = await AnalyticsRepository.get_resolution_time_buckets(db, days_back)
    top_agents = await AnalyticsRepository.get_top_performing_agents(db, limit=10, days_back=days_back)
    common_topics = await AnalyticsRepository.get_common_topics(db, days_back)
    rating_dist = await AnalyticsRepository.get_customer_ratings_distribution(db, days_back)
    operational_metrics = await AnalyticsRepository.get_operational_metrics(db, days_back)
    
    return {
        "kpi_metrics": kpi_metrics,
        "daily_call_volume": daily_volume,
        "hourly_distribution": hourly_dist,
        "sentiment_distribution": sentiment_dist,
        "call_categories": call_categories,
        "resolution_time_buckets": resolution_buckets,
        "top_agents": top_agents,
        "common_topics": common_topics,
        "rating_distribution": rating_dist,
        "operational_metrics": operational_metrics
    }


@router.get("/analytics/kpi")
async def get_kpi_metrics(
    days_back: int = Query(7, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get key performance indicators."""
    return await AnalyticsRepository.get_kpi_metrics(db, days_back)


@router.get("/analytics/call-volume")
async def get_call_volume_trend(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get daily call volume trend data."""
    return await AnalyticsRepository.get_daily_call_volume(db, days_back)


@router.get("/analytics/hourly-distribution")
async def get_hourly_distribution(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get hourly call distribution (peak hours)."""
    return await AnalyticsRepository.get_hourly_call_distribution(db, days_back)


@router.get("/analytics/sentiment")
async def get_sentiment_analysis(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get sentiment distribution analysis."""
    return await AnalyticsRepository.get_sentiment_distribution(db, days_back)


@router.get("/analytics/categories")
async def get_call_categories(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get call category/topic distribution."""
    return await AnalyticsRepository.get_call_categories(db, days_back)


@router.get("/analytics/resolution-time")
async def get_resolution_time_buckets(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get call resolution time distribution buckets."""
    return await AnalyticsRepository.get_resolution_time_buckets(db, days_back)


@router.get("/analytics/top-agents")
async def get_top_agents(
    limit: int = Query(10, description="Number of top agents to return"),
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get top performing agents."""
    return await AnalyticsRepository.get_top_performing_agents(db, limit, days_back)


@router.get("/analytics/topics")
async def get_common_topics(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get common call topics/categories."""
    return await AnalyticsRepository.get_common_topics(db, days_back)


@router.get("/analytics/ratings")
async def get_customer_ratings(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get customer satisfaction ratings distribution."""
    return await AnalyticsRepository.get_customer_ratings_distribution(db, days_back)


@router.get("/analytics/operational")
async def get_operational_metrics(
    days_back: int = Query(30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_session)
):
    """Get operational metrics (service level, occupancy, abandonment)."""
    return await AnalyticsRepository.get_operational_metrics(db, days_back)

