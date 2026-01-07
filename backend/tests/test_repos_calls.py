"""Tests for the calls repository layer."""

import pytest
from sqlalchemy.orm import Session
from backend.call_analytics_api.app.repos.calls import list_calls, get_call_details
from backend.common.models_db import Call, DialogueTurn, CallSummary


@pytest.mark.asyncio
async def test_list_calls(async_db_session, sample_call):
    """Test that list_calls returns calls with materialized fields."""
    # Add sample call to database
    async_db_session.add(sample_call)
    await async_db_session.commit()
    await async_db_session.refresh(sample_call)
    
    # Test listing calls
    result = await list_calls(async_db_session)
    
    assert len(result) == 1
    call = result[0]
    
    # Check that all expected fields are present
    assert call.id == sample_call.id
    assert call.external_job_id == "test-job-123"
    assert call.provider_call_id == "provider-call-456"
    assert call.agent_id == "agent-789"
    assert call.customer_number == "+1234567890"
    assert call.direction == "inbound"
    assert call.status == "completed"
    
    # Check materialized dashboard fields
    assert call.headline == "Test call about product inquiry"
    assert call.sentiment_label == "positive"
    assert call.duration_sec == 180


@pytest.mark.asyncio
async def test_list_calls_with_filtering(async_db_session, sample_call):
    """Test that list_calls works with filtering."""
    # Add sample call to database
    async_db_session.add(sample_call)
    await async_db_session.commit()
    await async_db_session.refresh(sample_call)
    
    # Test filtering by agent_id
    result = await list_calls(async_db_session, agent_id="agent-789")
    assert len(result) == 1
    
    result = await list_calls(async_db_session, agent_id="nonexistent-agent")
    assert len(result) == 0
    
    # Test filtering by direction
    result = await list_calls(async_db_session, direction="inbound")
    assert len(result) == 1
    
    result = await list_calls(async_db_session, direction="outbound")
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_call_details(async_db_session, sample_call, sample_dialogue_turns, sample_summary):
    """Test that get_call_details returns complete call information."""
    # Add sample data to database
    async_db_session.add(sample_call)
    await async_db_session.flush()  # Get the ID
    
    # Update dialogue turns and summary with correct call ID
    for turn in sample_dialogue_turns:
        turn.call_id = sample_call.id
        async_db_session.add(turn)
    
    sample_summary.call_id = sample_call.id
    async_db_session.add(sample_summary)
    
    await async_db_session.commit()
    await async_db_session.refresh(sample_call)
    
    # Test getting call details
    result = await get_call_details(async_db_session, sample_call.id)
    
    assert result is not None
    assert result.id == sample_call.id
    assert result.external_job_id == "test-job-123"
    assert result.provider_call_id == "provider-call-456"
    assert result.agent_id == "agent-789"
    assert result.customer_number == "+1234567890"
    assert result.direction == "inbound"
    assert result.status == "completed"
    
    # Check materialized dashboard fields
    assert result.headline == "Test call about product inquiry"
    assert result.sentiment_label == "positive"
    assert result.duration_sec == 180
    
    # Check dialogue turns are present and ordered
    assert len(result.dialogue_turns) == 2
    assert result.dialogue_turns[0].turn_index == 0
    assert result.dialogue_turns[1].turn_index == 1
    
    # Check summaries are present
    assert len(result.summaries) == 1
    assert result.summaries[0].summary_type == "llm_generated"
    assert result.summaries[0].payload["headline"] == "Product inquiry"


@pytest.mark.asyncio
async def test_get_call_details_not_found(async_db_session):
    """Test that get_call_details returns None for non-existent call."""
    result = await get_call_details(async_db_session, 999999)
    assert result is None