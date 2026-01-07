"""SQLAlchemy models for PostgreSQL database."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.db import Base


class Call(Base):
    """Model for storing call information."""
    
    __tablename__ = "calls"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_job_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    provider_call_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Renamed from call_id
    agent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    customer_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stt_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    
    # Snapshot-style entities / insights (non-canonical but still stored)
    entities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    
    # Materialized dashboard fields
    headline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Canonical FK links
    agent_fk: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # Relationship to dialogue turns
    dialogue_turns: Mapped[List["DialogueTurn"]] = relationship(
        "DialogueTurn", 
        back_populates="call", 
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Relationship to call summaries
    summaries: Mapped[List["CallSummary"]] = relationship(
        "CallSummary", 
        back_populates="call", 
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Relationships to canonical entities / business objects
    agent: Mapped[Optional["Agent"]] = relationship(
        "Agent",
        back_populates="calls",
        foreign_keys=[agent_fk],
    )
    person: Mapped[Optional["Person"]] = relationship(
        "Person",
        back_populates="calls",
        foreign_keys=[person_id],
    )
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        back_populates="calls",
        foreign_keys=[organization_id],
    )
    
    extractions: Mapped[List["Extraction"]] = relationship(
        "Extraction",
        back_populates="call",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    extracted_facts: Mapped[List["ExtractedFact"]] = relationship(
        "ExtractedFact",
        back_populates="call",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="call",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    offers: Mapped[List["Offer"]] = relationship(
        "Offer",
        back_populates="call",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    product_mentions: Mapped[List["CallProductMention"]] = relationship(
        "CallProductMention",
        back_populates="call",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    # Table constraints
    __table_args__ = (
        # CHECK constraints for enum-like fields
        # Note: These are enforced at the database level
        # Application code should also validate these values
    )


class DialogueTurn(Base):
    """Model for storing diarized dialogue turns within a call."""
    
    __tablename__ = "dialogue_turns"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("calls.id", ondelete="CASCADE"), 
        nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String, nullable=False)
    channel: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_sec: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    end_sec: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    
    # Relationship back to call
    call: Mapped["Call"] = relationship("Call", back_populates="dialogue_turns")
    
    # Indexes
    __table_args__ = (
        Index("idx_dialogue_turns_call_id", "call_id"),
        Index("idx_dialogue_turns_call_turn", "call_id", "turn_index"),
    )


class CallSummary(Base):
    """Model for storing call summaries."""
    
    __tablename__ = "call_summaries"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("calls.id", ondelete="CASCADE"), 
        nullable=False
    )
    summary_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    
    # Relationship back to call
    call: Mapped["Call"] = relationship("Call", back_populates="summaries")
    
    # Unique constraint to ensure only one summary per type per call
    __table_args__ = (
        # This ensures we only have one summary of each type per call
        # For example, only one 'llm_generated' summary per call
    )


class Agent(Base):
    """Canonical agent entity."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_agent_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    calls: Mapped[List["Call"]] = relationship(
        "Call",
        back_populates="agent",
        lazy="selectin",
    )


class Person(Base):
    """Canonical person (customer/contact)."""

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    given_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    family_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    calls: Mapped[List["Call"]] = relationship(
        "Call",
        back_populates="person",
        lazy="selectin",
    )


class Organization(Base):
    """Canonical organization/company."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    calls: Mapped[List["Call"]] = relationship(
        "Call",
        back_populates="organization",
        lazy="selectin",
    )


class Identifier(Base):
    """Identifiers like phone/email for people or organizations."""

    __tablename__ = "identifiers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    identifier_type: Mapped[str] = mapped_column(String, nullable=False)
    identifier_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)

    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    person: Mapped[Optional["Person"]] = relationship("Person", lazy="selectin")
    organization: Mapped[Optional["Organization"]] = relationship("Organization", lazy="selectin")


class Address(Base):
    """Physical address."""

    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line1: Mapped[str] = mapped_column(String, nullable=False)
    line2: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EntityAddress(Base):
    """Links an address to either a person or an organization."""

    __tablename__ = "entity_addresses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    address_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("addresses.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    address_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=func.false()
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    address: Mapped["Address"] = relationship("Address", lazy="selectin")
    person: Mapped[Optional["Person"]] = relationship("Person", lazy="selectin")
    organization: Mapped[Optional["Organization"]] = relationship("Organization", lazy="selectin")


class Extraction(Base):
    """One extraction run per call (LLM output, etc.)."""

    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    extractor_name: Mapped[str] = mapped_column(String, nullable=False)
    extractor_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    run_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="succeeded")
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    call: Mapped["Call"] = relationship("Call", back_populates="extractions")
    facts: Mapped[List["ExtractedFact"]] = relationship(
        "ExtractedFact",
        back_populates="extraction",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ExtractedFact(Base):
    """Atomic extracted fact/claim with provenance and confidence."""

    __tablename__ = "extracted_facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    extraction_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("extractions.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    fact_type: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="proposed")
    confidence: Mapped[float] = mapped_column(Double, nullable=False)
    turn_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("dialogue_turns.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_sec: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    end_sec: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    raw_span_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    offer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("offers.id", ondelete="SET NULL"),
        nullable=True,
    )
    stable_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    extraction: Mapped["Extraction"] = relationship("Extraction", back_populates="facts")
    call: Mapped["Call"] = relationship("Call", back_populates="extracted_facts")
    turn: Mapped[Optional["DialogueTurn"]] = relationship("DialogueTurn", lazy="selectin")


class Product(Base):
    """Optional product catalog."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sku: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Task(Base):
    """Action item derived from a call."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extractions.id", ondelete="SET NULL"),
        nullable=True,
    )
    fact_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extracted_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    due_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    owner_agent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    stable_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    call: Mapped["Call"] = relationship("Call", back_populates="tasks")
    extraction: Mapped[Optional["Extraction"]] = relationship("Extraction", lazy="selectin")
    fact: Mapped[Optional["ExtractedFact"]] = relationship("ExtractedFact", foreign_keys=[fact_id], lazy="selectin")
    owner_agent: Mapped[Optional["Agent"]] = relationship("Agent", lazy="selectin")
    person: Mapped[Optional["Person"]] = relationship("Person", lazy="selectin")
    organization: Mapped[Optional["Organization"]] = relationship("Organization", lazy="selectin")


class Offer(Base):
    """Discount / promise / quote derived from a call."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    extraction_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extractions.id", ondelete="SET NULL"),
        nullable=True,
    )
    fact_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extracted_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="promised")
    discount_amount: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    discount_percent: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    price_amount: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    price_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stable_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    call: Mapped["Call"] = relationship("Call", back_populates="offers")
    extraction: Mapped[Optional["Extraction"]] = relationship("Extraction", lazy="selectin")
    fact: Mapped[Optional["ExtractedFact"]] = relationship("ExtractedFact", foreign_keys=[fact_id], lazy="selectin")
    product: Mapped[Optional["Product"]] = relationship("Product", lazy="selectin")
    person: Mapped[Optional["Person"]] = relationship("Person", lazy="selectin")
    organization: Mapped[Optional["Organization"]] = relationship("Organization", lazy="selectin")


class CallProductMention(Base):
    """Product mention within a specific call."""

    __tablename__ = "call_product_mentions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    extraction_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extractions.id", ondelete="SET NULL"),
        nullable=True,
    )
    fact_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extracted_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    mentioned_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_amount: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    price_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_sec: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    end_sec: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    stable_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    call: Mapped["Call"] = relationship("Call", back_populates="product_mentions")
    extraction: Mapped[Optional["Extraction"]] = relationship("Extraction", lazy="selectin")
    fact: Mapped[Optional["ExtractedFact"]] = relationship("ExtractedFact", foreign_keys=[fact_id], lazy="selectin")
    product: Mapped[Optional["Product"]] = relationship("Product", lazy="selectin")
    person: Mapped[Optional["Person"]] = relationship("Person", lazy="selectin")
    organization: Mapped[Optional["Organization"]] = relationship("Organization", lazy="selectin")