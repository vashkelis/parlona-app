"""Repository layer for call-related database operations."""

from typing import List, Optional
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.common.models_db import (
    Call,
    DialogueTurn,
    CallSummary,
    Person,
    Task,
    Offer,
    CallProductMention,
    ExtractedFact,
    Identifier,
)
from backend.call_analytics_api.app.schemas_db import (
    CallListItemOut,
    CallDetailsOut,
    DialogueTurnOut,
    CallSummaryOut,
    CallListResponse,
)
from backend.call_analytics_api.app.schemas_business import (
    PersonSummaryOut,
    PersonDetailsOut,
    TaskOut,
    OfferOut,
    ProductMentionOut,
    ExtractedFactOut,
)
from backend.call_analytics_api.app.repos.tasks import get_tasks_for_call
from backend.call_analytics_api.app.repos.offers import get_offers_for_call
from backend.call_analytics_api.app.repos.customers import get_customer_details


async def list_calls(
    db: AsyncSession,
    agent_id: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> CallListResponse:
    """List calls with optional filtering - optimized for dashboard queries."""
    # Base query for items
    query = (
        select(Call)
        .options(
            joinedload(Call.person),
            selectinload(Call.tasks),
            selectinload(Call.offers),
        )
        .order_by(desc(Call.created_at))
    )
    
    # Base query for count
    count_query = select(func.count()).select_from(Call)
    
    if agent_id:
        query = query.where(Call.agent_id == agent_id)
        count_query = count_query.where(Call.agent_id == agent_id)
    
    if direction:
        query = query.where(Call.direction == direction)
        count_query = count_query.where(Call.direction == direction)
    
    # Execute count
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0
    
    # Execute items
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    calls = result.scalars().all()
    
    # Convert to Pydantic models with identity and counts
    items = []
    for call in calls:
        # Build caller identity summary
        caller_identity = None
        if call.person:
            # Get primary phone for display
            primary_phone_result = await db.execute(
                select(Identifier.identifier_value)
                .where(
                    Identifier.person_id == call.person.id,
                    Identifier.identifier_type == "phone"
                )
                .limit(1)
            )
            primary_phone = primary_phone_result.scalar_one_or_none()
            
            display_label = call.person.full_name or primary_phone or f"Customer #{call.person.id}"
            caller_identity = PersonSummaryOut(
                id=call.person.id,
                full_name=call.person.full_name,
                display_label=display_label,
            )
        
        # Count open tasks
        open_tasks_count = sum(1 for t in call.tasks if t.status == "open")
        
        # Count offers
        offers_count = len(call.offers)
        
        items.append(CallListItemOut(
            id=call.id,
            external_job_id=call.external_job_id,
            provider_call_id=call.provider_call_id,
            agent_id=call.agent_id,
            customer_number=call.customer_number,
            direction=call.direction,
            started_at=call.started_at,
            ended_at=call.ended_at,
            status=call.status,
            headline=call.headline,
            sentiment_label=call.sentiment_label,
            duration_sec=call.duration_sec,
            person_id=call.person_id,
            caller_identity=caller_identity,
            open_tasks_count=open_tasks_count,
            offers_count=offers_count,
            created_at=call.created_at,
        ))
    
    return CallListResponse(items=items, total_count=total_count)


async def get_call_details(db: AsyncSession, call_id: int) -> Optional[CallDetailsOut]:
    """Get detailed call information with dialogue turns, summaries, and business objects."""
    # Fetch the call with relationships
    call_result = await db.execute(
        select(Call)
        .options(
            joinedload(Call.person),
            selectinload(Call.dialogue_turns),
            selectinload(Call.summaries),
        )
        .where(Call.id == call_id)
    )
    call = call_result.scalar_one_or_none()
    
    if not call:
        return None
    
    # Build caller identity summary
    caller_identity = None
    if call.person:
        caller_identity = await get_customer_details(db, call.person.id)
    
    # Get tasks for this call
    tasks = await get_tasks_for_call(db, call_id)
    
    # Get offers for this call
    offers = await get_offers_for_call(db, call_id)
    
    # Get product mentions
    product_mentions_result = await db.execute(
        select(CallProductMention)
        .where(CallProductMention.call_id == call_id)
        .order_by(CallProductMention.start_sec)
    )
    product_mentions_db = product_mentions_result.scalars().all()
    product_mentions = [
        ProductMentionOut.model_validate(pm) for pm in product_mentions_db
    ]
    
    # Get extracted facts (optional, can be large)
    extracted_facts_result = await db.execute(
        select(ExtractedFact)
        .where(ExtractedFact.call_id == call_id)
        .order_by(ExtractedFact.created_at)
        .limit(50)  # Limit to avoid huge payloads
    )
    extracted_facts_db = extracted_facts_result.scalars().all()
    extracted_facts = [
        ExtractedFactOut.model_validate(ef) for ef in extracted_facts_db
    ]
    
    # Convert to Pydantic model
    return CallDetailsOut(
        id=call.id,
        external_job_id=call.external_job_id,
        provider_call_id=call.provider_call_id,
        agent_id=call.agent_id,
        customer_number=call.customer_number,
        direction=call.direction,
        audio_path=call.audio_path,
        started_at=call.started_at,
        ended_at=call.ended_at,
        language=call.language,
        stt_model=call.stt_model,
        status=call.status,
        headline=call.headline,
        sentiment_label=call.sentiment_label,
        sentiment_score=call.sentiment_score,
        duration_sec=call.duration_sec,
        created_at=call.created_at,
        updated_at=call.updated_at,
        dialogue_turns=[DialogueTurnOut.model_validate(dt) for dt in call.dialogue_turns],
        summaries=[CallSummaryOut.model_validate(cs) for cs in call.summaries],
        caller_identity=caller_identity,
        tasks=tasks,
        offers=offers,
        product_mentions=product_mentions,
        extracted_facts=extracted_facts,
        entities=call.entities,
        intent=call.intent,
        resolution=call.resolution,
        confidence_score=call.confidence_score,
    )