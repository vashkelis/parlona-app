"""
Integration tests for the complete pipeline.
These tests verify that the summarization service works correctly with the LLM integration.
"""

import pytest
import time
from unittest.mock import Mock, patch

from backend.common.config import Settings
from backend.common.models import Job, JobStatus, QueueMessage
from backend.common.redis_utils import enqueue_stt_job, get_job
from backend.summary_service.app.worker import SummaryWorker


@pytest.mark.integration
def test_end_to_end_summarization_pipeline():
    """Test the complete summarization pipeline with mocked LLM."""
    # This is a placeholder for integration tests
    # In a real scenario, this would test the complete pipeline
    pass


# Skip this test for now as it requires a running Redis instance
@pytest.mark.skip(reason="Requires running Redis instance")
def test_summary_worker_integration():
    """Integration test for the summary worker with a real Redis instance."""
    settings = Settings()
    
    # Create a test job
    job_id = "test-integration-job"
    test_transcript = "Hello, this is a test conversation for summarization. We are testing the LLM integration."
    
    # Create job in Redis
    job = Job(
        job_id=job_id,
        status=JobStatus.stt_done,
        stt_text=test_transcript
    )
    
    # Enqueue the job for summarization
    enqueue_stt_job(QueueMessage(job_id=job_id))
    
    # Create and run the summary worker
    worker = SummaryWorker(settings)
    
    # Mock the LLM client to return a predefined summary
    worker.llm_client.summarize = Mock(return_value=("This is a test summary of the conversation.", "en"))
    
    # Process one message
    with patch.object(worker, '_stopping', True):  # Stop after one iteration
        worker.run()
    
    # Check that the job was updated with the summary
    updated_job = get_job(job_id)
    assert updated_job.status == JobStatus.summary_done
    assert "test summary" in updated_job.dummy_summary.lower()
    assert "en" in updated_job.dummy_tags