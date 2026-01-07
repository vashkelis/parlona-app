"""Tests for the Pydantic schemas."""

import pytest
from datetime import datetime
from backend.call_analytics_api.app.schemas_db import CallListItemOut, CallDetailsOut, DialogueTurnOut, CallSummaryOut


def test_call_list_item_out():
    """Test that CallListItemOut schema works correctly."""
    # Create a sample call list item
    call_data = {
        "id": 1,
        "external_job_id": "job-123",
        "provider_call_id": "provider-456",
        "agent_id": "agent-789",
        "customer_number": "+1234567890",
        "direction": "inbound",
        "started_at": "2023-01-01T10:00:00",
        "ended_at": "2023-01-01T10:03:00",
        "status": "completed",
        "headline": "Test call about product inquiry",
        "sentiment_label": "positive",
        "duration_sec": 180,
        "created_at": "2023-01-01T10:05:00"
    }
    
    call = CallListItemOut(**call_data)
    
    # Check that all fields are correctly set
    assert call.id == 1
    assert call.external_job_id == "job-123"
    assert call.provider_call_id == "provider-456"
    assert call.agent_id == "agent-789"
    assert call.customer_number == "+1234567890"
    assert call.direction == "inbound"
    assert call.status == "completed"
    assert call.headline == "Test call about product inquiry"
    assert call.sentiment_label == "positive"
    assert call.duration_sec == 180


def test_call_details_out():
    """Test that CallDetailsOut schema works correctly."""
    # Create sample dialogue turns
    dialogue_turns = [
        DialogueTurnOut(
            id=1,
            call_id=1,
            turn_index=0,
            speaker="agent",
            channel=None,
            start_sec=0.0,
            end_sec=3.5,
            text="Hello, how can I help you today?",
            created_at="2023-01-01T10:00:00"
        ),
        DialogueTurnOut(
            id=2,
            call_id=1,
            turn_index=1,
            speaker="customer",
            channel=None,
            start_sec=3.5,
            end_sec=7.2,
            text="I'd like to inquire about your products.",
            created_at="2023-01-01T10:00:05"
        )
    ]
    
    # Create sample summaries
    summaries = [
        CallSummaryOut(
            id=1,
            call_id=1,
            summary_type="llm_generated",
            model="openai_gpt",
            created_at="2023-01-01T10:05:00",
            payload={
                "headline": "Product inquiry",
                "text": "Customer called to inquire about products.",
                "tags": ["product", "inquiry"]
            }
        )
    ]
    
    # Create a sample call with all details
    call_data = {
        "id": 1,
        "external_job_id": "job-123",
        "provider_call_id": "provider-456",
        "agent_id": "agent-789",
        "customer_number": "+1234567890",
        "direction": "inbound",
        "audio_path": "/path/to/audio.wav",
        "started_at": "2023-01-01T10:00:00",
        "ended_at": "2023-01-01T10:03:00",
        "language": "en",
        "stt_model": "whisper",
        "status": "completed",
        "headline": "Test call about product inquiry",
        "sentiment_label": "positive",
        "sentiment_score": 0.85,
        "duration_sec": 180,
        "created_at": "2023-01-01T10:05:00",
        "updated_at": "2023-01-01T10:05:00",
        "dialogue_turns": [dt.model_dump() for dt in dialogue_turns],
        "summaries": [s.model_dump() for s in summaries]
    }
    
    call = CallDetailsOut(**call_data)
    
    # Check that all fields are correctly set
    assert call.id == 1
    assert call.external_job_id == "job-123"
    assert call.provider_call_id == "provider-456"
    assert call.agent_id == "agent-789"
    assert call.customer_number == "+1234567890"
    assert call.direction == "inbound"
    assert call.status == "completed"
    assert call.headline == "Test call about product inquiry"
    assert call.sentiment_label == "positive"
    assert call.sentiment_score == 0.85
    assert call.duration_sec == 180
    assert call.audio_path == "/path/to/audio.wav"
    assert call.language == "en"
    assert call.stt_model == "whisper"
    
    # Check dialogue turns
    assert len(call.dialogue_turns) == 2
    assert call.dialogue_turns[0].turn_index == 0
    assert call.dialogue_turns[0].speaker == "agent"
    assert call.dialogue_turns[1].turn_index == 1
    assert call.dialogue_turns[1].speaker == "customer"
    
    # Check summaries
    assert len(call.summaries) == 1
    assert call.summaries[0].summary_type == "llm_generated"
    assert call.summaries[0].payload["headline"] == "Product inquiry"