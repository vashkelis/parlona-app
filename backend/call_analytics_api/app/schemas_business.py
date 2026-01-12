"""Pydantic schemas for business objects: customers, tasks, offers."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# ============ Identifier Schemas ============

class IdentifierOut(BaseModel):
    """Schema for identifier output."""
    id: int
    identifier_type: str
    identifier_value: str
    normalized_value: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Address Schemas ============

class AddressOut(BaseModel):
    """Schema for address output."""
    id: int
    line1: str
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    address_type: Optional[str] = None
    is_primary: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Person/Customer Schemas ============

class PersonSummaryOut(BaseModel):
    """Schema for person summary - used in embedded contexts."""
    id: int
    full_name: Optional[str] = None
    display_label: Optional[str] = None  # Computed: full_name or primary phone
    
    class Config:
        from_attributes = True


class PersonListItemOut(BaseModel):
    """Schema for person list items - optimized for customers list page."""
    id: int
    full_name: Optional[str] = None
    display_label: str  # Computed: full_name or primary phone
    primary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    call_count: int = 0
    open_tasks_count: int = 0
    last_contact_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PersonDetailsOut(BaseModel):
    """Schema for detailed person/customer information."""
    id: int
    full_name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    display_label: str
    date_of_birth: Optional[datetime] = None
    id_number: Optional[str] = None
    
    # Identifiers
    identifiers: List[IdentifierOut] = []
    primary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    
    # Addresses
    addresses: List[AddressOut] = []
    
    # Associated organization (if any)
    organization_name: Optional[str] = None
    organization_id: Optional[int] = None
    
    # Statistics
    call_count: int = 0
    open_tasks_count: int = 0
    total_tasks_count: int = 0
    offers_count: int = 0
    first_contact_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Task Schemas ============

class TaskOut(BaseModel):
    """Schema for task output."""
    id: int
    call_id: int
    title: str
    description: Optional[str] = None
    status: str  # open, in_progress, completed, cancelled
    due_at: Optional[datetime] = None
    
    # Relations
    owner_agent_id: Optional[int] = None
    owner_agent_name: Optional[str] = None
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    organization_id: Optional[int] = None
    
    # Provenance
    extraction_id: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskUpdateIn(BaseModel):
    """Schema for task update."""
    status: Optional[str] = None
    due_at: Optional[datetime] = None
    owner_agent_id: Optional[int] = None
    description: Optional[str] = None


class TaskListItemOut(BaseModel):
    """Schema for task list items - optimized for tasks list page."""
    id: int
    call_id: int
    title: str
    status: str
    due_at: Optional[datetime] = None
    
    # Minimal context
    person_name: Optional[str] = None
    owner_agent_name: Optional[str] = None
    call_headline: Optional[str] = None
    call_date: Optional[datetime] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Offer Schemas ============

class OfferOut(BaseModel):
    """Schema for offer output."""
    id: int
    call_id: int
    description: str
    status: str  # promised, fulfilled, expired, cancelled
    
    # Financial details
    discount_amount: Optional[float] = None
    discount_percent: Optional[float] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    
    # Validity
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    conditions: Optional[str] = None
    
    # Relations
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    organization_id: Optional[int] = None
    product_id: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OfferUpdateIn(BaseModel):
    """Schema for offer update."""
    status: Optional[str] = None
    valid_until: Optional[datetime] = None


# ============ Organization Schemas ============

class OrganizationOut(BaseModel):
    """Schema for organization output."""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Product Mention Schemas ============

class ProductMentionOut(BaseModel):
    """Schema for product mention output."""
    id: int
    call_id: int
    mentioned_name: str
    quantity: Optional[float] = None
    quantity_unit: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    context: Optional[str] = None
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Extracted Fact Schemas ============

class ExtractedFactOut(BaseModel):
    """Schema for extracted fact output."""
    id: int
    fact_type: str
    label: Optional[str] = None
    value: dict
    status: str  # proposed, accepted, rejected
    confidence: float
    
    # Provenance
    turn_id: Optional[int] = None
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    raw_span_text: Optional[str] = None
    
    created_at: datetime

    class Config:
        from_attributes = True
