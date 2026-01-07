"""Tests for the /v1/calls endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.call_analytics_api.app.main import app
from backend.common.models_db import Call, DialogueTurn, CallSummary


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def populated_db(db_session: Session, sample_call, sample_dialogue_turns, sample_summary):
    """Populate the test database with sample data."""
    # Add the sample call
    db_session.add(sample_call)
    db_session.flush()  # Get the ID
    
    # Update dialogue turns with the correct call ID
    for turn in sample_dialogue_turns:
        turn.call_id = sample_call.id
        db_session.add(turn)
    
    # Update summary with the correct call ID
    sample_summary.call_id = sample_call.id
    db_session.add(sample_summary)
    
    db_session.commit()
    return db_session


def test_list_calls_endpoint(client, populated_db):
    """Test that /v1/calls returns materialized fields."""
    response = client.get("/v1/calls")
    
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    assert len(data) == 1
    
    call = data[0]
    assert call["id"] is not None
    assert call["external_job_id"] == "test-job-123"
    assert call["provider_call_id"] == "provider-call-456"
    assert call["agent_id"] == "agent-789"
    assert call["customer_number"] == "+1234567890"
    assert call["direction"] == "inbound"
    assert call["status"] == "completed"
    
    # Check that materialized dashboard fields are present
    assert call["headline"] == "Test call about product inquiry"
    assert call["sentiment_label"] == "positive"
    assert call["duration_sec"] == 180
    
    # Check that non-dashboard fields are not present in list view
    assert "audio_path" not in call
    assert "language" not in call
    assert "stt_model" not in call
    assert "sentiment_score" not in call


def test_get_call_endpoint(client, populated_db, sample_call):
    """Test that /v1/calls/{id} returns ordered turns and full details."""
    response = client.get(f"/v1/calls/{sample_call.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check basic call fields
    assert data["id"] == sample_call.id
    assert data["external_job_id"] == "test-job-123"
    assert data["provider_call_id"] == "provider-call-456"
    assert data["agent_id"] == "agent-789"
    assert data["customer_number"] == "+1234567890"
    assert data["direction"] == "inbound"
    assert data["status"] == "completed"
    
    # Check materialized dashboard fields
    assert data["headline"] == "Test call about product inquiry"
    assert data["sentiment_label"] == "positive"
    assert data["duration_sec"] == 180
    
    # Check that all call fields are present in detail view
    assert "audio_path" in data
    assert "language" in data
    assert "stt_model" in data
    assert "sentiment_score" in data
    
    # Check dialogue turns are present and ordered
    assert "dialogue_turns" in data
    assert isinstance(data["dialogue_turns"], list)
    assert len(data["dialogue_turns"]) == 2
    
    # Check turns are ordered by turn_index
    assert data["dialogue_turns"][0]["turn_index"] == 0
    assert data["dialogue_turns"][1]["turn_index"] == 1
    
    # Check turn content
    assert data["dialogue_turns"][0]["speaker"] == "agent"
    assert data["dialogue_turns"][0]["text"] == "Hello, how can I help you today?"
    
    assert data["dialogue_turns"][1]["speaker"] == "customer"
    assert data["dialogue_turns"][1]["text"] == "I'd like to inquire about your products."
    
    # Check summaries are present
    assert "summaries" in data
    assert isinstance(data["summaries"], list)
    assert len(data["summaries"]) == 1
    
    summary = data["summaries"][0]
    assert summary["summary_type"] == "llm_generated"
    assert summary["payload"]["headline"] == "Product inquiry"


def test_get_call_endpoint_not_found(client):
    """Test that /v1/calls/{id} returns 404 for non-existent call."""
    response = client.get("/v1/calls/999999")
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Call not found"