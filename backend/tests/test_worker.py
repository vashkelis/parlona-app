"""Tests for the postprocess service worker."""

import pytest
from unittest.mock import Mock, patch
from backend.postprocess_service.app.worker import PostprocessWorker
from backend.common.models import JobStatus, JobMetadata
from backend.common.models_db import Call, DialogueTurn, CallSummary


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.queue_poll_timeout = 1
    return settings


@pytest.fixture
def worker(mock_settings):
    """Create a PostprocessWorker instance for testing."""
    return PostprocessWorker(mock_settings)


def test_calculate_duration_sec_from_started_ended(worker):
    """Test duration calculation from started_at and ended_at."""
    from datetime import datetime, timezone
    
    # Create a mock call with started_at and ended_at
    call_record = Call()
    call_record.started_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    call_record.ended_at = datetime(2023, 1, 1, 10, 3, 0, tzinfo=timezone.utc)
    
    # Create a mock job
    job = JobMetadata(
        job_id="test-job",
        status=JobStatus.done,
        audio_path="/test/audio.wav",
        stt_language="en",
        stt_engine="whisper",
        stt_segments=[]
    )
    
    duration = worker._calculate_duration_sec(job, call_record)
    assert duration == 180  # 3 minutes = 180 seconds


def test_calculate_duration_sec_from_stt_segments(worker):
    """Test duration calculation from STT segments."""
    # Create a mock call without started_at/ended_at
    call_record = Call()
    call_record.started_at = None
    call_record.ended_at = None
    
    # Create a mock job with STT segments
    job = JobMetadata(
        job_id="test-job",
        status=JobStatus.done,
        audio_path="/test/audio.wav",
        stt_language="en",
        stt_engine="whisper",
        stt_segments=[
            {"start": 0.0, "end": 5.5, "text": "Hello"},
            {"start": 5.5, "end": 12.3, "text": "World"},
            {"start": 12.3, "end": 18.7, "text": "Test"}
        ]
    )
    
    duration = worker._calculate_duration_sec(job, call_record)
    assert duration == 18  # Max end time is 18.7, rounded down to 18


def test_calculate_duration_sec_no_data(worker):
    """Test duration calculation when no data is available."""
    # Create a mock call without started_at/ended_at
    call_record = Call()
    call_record.started_at = None
    call_record.ended_at = None
    
    # Create a mock job with no STT segments
    job = JobMetadata(
        job_id="test-job",
        status=JobStatus.done,
        audio_path="/test/audio.wav",
        stt_language="en",
        stt_engine="whisper",
        stt_segments=[]
    )
    
    duration = worker._calculate_duration_sec(job, call_record)
    assert duration is None


@patch('backend.postprocess_service.app.worker.get_job')
@patch('backend.postprocess_service.app.worker.update_job')
@patch('backend.postprocess_service.app.worker.SessionLocal')
@pytest.mark.asyncio
async def test_persist_to_database_materializes_fields(
    mock_session_local, 
    mock_update_job, 
    mock_get_job, 
    worker
):
    """Test that persist_to_database materializes dashboard fields from summaries."""
    # Mock the database session
    mock_session = Mock()
    mock_session_local.return_value = mock_session
    mock_session.execute.return_value = Mock(scalar_one_or_none=lambda: None)
    
    # Mock job data with summary
    job_data = JobMetadata(
        job_id="test-job-123",
        status=JobStatus.done,
        audio_path="/test/audio.wav",
        stt_language="en",
        stt_engine="whisper",
        stt_segments=[
            {"start": 0.0, "end": 5.5, "speaker": "agent", "text": "Hello"},
            {"start": 5.5, "end": 12.3, "speaker": "customer", "text": "Hi there"}
        ],
        dummy_summary="Customer called to inquire about products.",
        dummy_headline="Product Inquiry",
        extra_meta={
            "agent_id": "agent-789",
            "customer_number": "+1234567890",
            "direction": "inbound",
            "call_id": "provider-call-456"  # This should be mapped to provider_call_id
        }
    )
    
    mock_get_job.return_value = job_data
    
    # Call the persist method (this will run the async function internally)
    worker._persist_to_database(job_data)
    
    # Verify that the session methods were called
    assert mock_session.add.called
    assert mock_session.flush.called
    assert mock_session.commit.called
    
    # Check that a Call object was created with the right fields
    call_args = [args[0] for args, kwargs in mock_session.add.call_args_list if isinstance(args[0], Call)]
    assert len(call_args) >= 1
    call_record = call_args[0]
    
    # Check basic fields
    assert call_record.external_job_id == "test-job-123"
    assert call_record.provider_call_id == "provider-call-456"  # Renamed field
    assert call_record.agent_id == "agent-789"
    assert call_record.customer_number == "+1234567890"
    assert call_record.direction == "inbound"
    assert call_record.status == "completed"
    
    # Check that dashboard fields were materialized
    assert call_record.headline == "Product Inquiry"
    assert call_record.duration_sec == 12  # Max end time from STT segments (12.3) rounded down