"""Repository layer for offer-related database operations."""

from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.common.models_db import Offer, Person
from backend.call_analytics_api.app.schemas_business import OfferOut


async def get_offers_for_person(
    db: AsyncSession,
    person_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[OfferOut]:
    """Get offers associated with a specific person."""
    
    stmt = (
        select(Offer)
        .options(joinedload(Offer.person))
        .where(Offer.person_id == person_id)
        .order_by(desc(Offer.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    offers = result.scalars().all()
    
    # Build output
    output = []
    for offer in offers:
        person_name = None
        if offer.person:
            person_name = offer.person.full_name
        
        output.append(OfferOut(
            id=offer.id,
            call_id=offer.call_id,
            description=offer.description,
            status=offer.status,
            discount_amount=offer.discount_amount,
            discount_percent=offer.discount_percent,
            price_amount=offer.price_amount,
            price_currency=offer.price_currency,
            valid_from=offer.valid_from,
            valid_until=offer.valid_until,
            conditions=offer.conditions,
            person_id=offer.person_id,
            person_name=person_name,
            organization_id=offer.organization_id,
            product_id=offer.product_id,
            created_at=offer.created_at,
            updated_at=offer.updated_at,
        ))
    
    return output


async def get_offers_for_call(
    db: AsyncSession,
    call_id: int
) -> List[OfferOut]:
    """Get offers associated with a specific call."""
    
    stmt = (
        select(Offer)
        .options(joinedload(Offer.person))
        .where(Offer.call_id == call_id)
        .order_by(Offer.created_at)
    )
    
    result = await db.execute(stmt)
    offers = result.scalars().all()
    
    # Build output
    output = []
    for offer in offers:
        person_name = None
        if offer.person:
            person_name = offer.person.full_name
        
        output.append(OfferOut(
            id=offer.id,
            call_id=offer.call_id,
            description=offer.description,
            status=offer.status,
            discount_amount=offer.discount_amount,
            discount_percent=offer.discount_percent,
            price_amount=offer.price_amount,
            price_currency=offer.price_currency,
            valid_from=offer.valid_from,
            valid_until=offer.valid_until,
            conditions=offer.conditions,
            person_id=offer.person_id,
            person_name=person_name,
            organization_id=offer.organization_id,
            product_id=offer.product_id,
            created_at=offer.created_at,
            updated_at=offer.updated_at,
        ))
    
    return output
