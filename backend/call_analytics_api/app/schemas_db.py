"""Pydantic schemas for database models."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, computed_field

from backend.call_analytics_api.app.schemas_business import (
    PersonSummaryOut,
    TaskOut,
    OfferOut,
    ProductMentionOut,
    ExtractedFactOut,
)


class CallOut(BaseModel):
    """Schema for call output."""
    id: int
    external_job_id: str
    provider_call_id: Optional[str] = None  # Renamed from call_id
    agent_id: Optional[str] = None
    customer_number: Optional[str] = None
    direction: Optional[str] = None
    audio_path: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    language: Optional[str] = None
    stt_model: Optional[str] = None
    status: str
    
    # Materialized dashboard fields
    headline: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    duration_sec: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DialogueTurnOut(BaseModel):
    """Schema for dialogue turn output."""
    id: int
    call_id: int
    turn_index: int
    speaker: str
    channel: Optional[int] = None
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    text: str
    created_at: datetime

    class Config:
        from_attributes = True


class CallSummaryOut(BaseModel):
    """Schema for call summary output."""
    id: int
    call_id: int
    summary_type: str
    model: Optional[str] = None
    created_at: datetime
    payload: Optional[dict] = None

    class Config:
        from_attributes = True


class CallWithDialogueOut(CallOut):
    """Schema for call with dialogue turns."""
    dialogue_turns: List[DialogueTurnOut] = []
    summaries: List[CallSummaryOut] = []

    class Config:
        from_attributes = True


# New explicit response models for better API contracts
class CallListItemOut(BaseModel):
    """Schema for call list items - optimized for dashboard queries."""
    id: int
    external_job_id: str
    provider_call_id: Optional[str] = None
    agent_id: Optional[str] = None
    customer_number: Optional[str] = None
    direction: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: str
    
    # Materialized dashboard fields
    headline: Optional[str] = None
    sentiment_label: Optional[str] = None
    duration_sec: Optional[int] = None
    
    # Identity info
    person_id: Optional[int] = None
    caller_identity: Optional[PersonSummaryOut] = None
    
    # Counts
    open_tasks_count: int = 0
    offers_count: int = 0
    
    created_at: datetime

    class Config:
        from_attributes = True


class CallDetailsOut(CallOut):
    """Schema for detailed call information."""
    dialogue_turns: List[DialogueTurnOut] = []
    summaries: List[CallSummaryOut] = []
    
    # Business objects linked to this call
    caller_identity: Optional[PersonSummaryOut] = None
    tasks: List[TaskOut] = []
    offers: List[OfferOut] = []
    product_mentions: List[ProductMentionOut] = []
    extracted_facts: List[ExtractedFactOut] = []
    
    # Entity/intent insights (snapshot-style, for backward compat)
    entities: Optional[dict] = None
    intent: Optional[str] = None
    resolution: Optional[str] = None
    confidence_score: Optional[float] = None

    class Config:
        from_attributes = True