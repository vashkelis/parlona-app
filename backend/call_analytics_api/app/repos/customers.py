"""Repository layer for customer/person-related database operations."""

from typing import List, Optional
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.common.models_db import Person, Identifier, Organization, Call, Task, Address, EntityAddress
from backend.call_analytics_api.app.schemas_business import (
    PersonListItemOut,
    PersonDetailsOut,
    IdentifierOut,
    AddressOut,
)


async def list_customers(
    db: AsyncSession,
    query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[PersonListItemOut]:
    """List customers/people with optional search - optimized for customers list page."""
    
    # Base query
    stmt = select(Person).order_by(desc(Person.updated_at))
    
    # Apply search filter if provided
    if query:
        search_pattern = f"%{query}%"
        stmt = stmt.where(
            (Person.full_name.ilike(search_pattern)) |
            (Person.given_name.ilike(search_pattern)) |
            (Person.family_name.ilike(search_pattern))
        )
    
    stmt = stmt.limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    people = result.scalars().all()
    
    # Build output with computed fields
    output = []
    for person in people:
        # Get primary phone
        primary_phone = await _get_primary_identifier(db, person.id, "phone")
        primary_email = await _get_primary_identifier(db, person.id, "email")
        
        # Get call count
        call_count_result = await db.execute(
            select(func.count(Call.id)).where(Call.person_id == person.id)
        )
        call_count = call_count_result.scalar() or 0
        
        # Get open tasks count
        open_tasks_result = await db.execute(
            select(func.count(Task.id)).where(
                Task.person_id == person.id,
                Task.status == "open"
            )
        )
        open_tasks_count = open_tasks_result.scalar() or 0
        
        # Get last contact date
        last_call_result = await db.execute(
            select(Call.created_at)
            .where(Call.person_id == person.id)
            .order_by(desc(Call.created_at))
            .limit(1)
        )
        last_contact_at = last_call_result.scalar_one_or_none()
        
        # Compute display label
        display_label = person.full_name or primary_phone or f"Customer #{person.id}"
        
        output.append(PersonListItemOut(
            id=person.id,
            full_name=person.full_name,
            display_label=display_label,
            primary_phone=primary_phone,
            primary_email=primary_email,
            call_count=call_count,
            open_tasks_count=open_tasks_count,
            last_contact_at=last_contact_at,
            created_at=person.created_at,
        ))
    
    return output


async def get_customer_details(
    db: AsyncSession,
    person_id: int
) -> Optional[PersonDetailsOut]:
    """Get detailed customer/person information with stats."""
    
    # Fetch person
    person_result = await db.execute(
        select(Person).where(Person.id == person_id)
    )
    person = person_result.scalar_one_or_none()
    
    if not person:
        return None
    
    # Get all identifiers
    identifiers_result = await db.execute(
        select(Identifier)
        .where(Identifier.person_id == person_id)
        .order_by(Identifier.identifier_type, Identifier.created_at)
    )
    identifiers = identifiers_result.scalars().all()
    identifiers_out = [IdentifierOut.model_validate(i) for i in identifiers]
    
    # Get all addresses
    addresses_result = await db.execute(
        select(Address, EntityAddress.address_type, EntityAddress.is_primary)
        .join(EntityAddress, EntityAddress.address_id == Address.id)
        .where(EntityAddress.person_id == person_id)
        .order_by(EntityAddress.is_primary.desc(), Address.created_at)
    )
    
    addresses_out = []
    for addr, addr_type, is_primary in addresses_result:
        addr_out = AddressOut(
            id=addr.id,
            line1=addr.line1,
            line2=addr.line2,
            city=addr.city,
            state=addr.state,
            postal_code=addr.postal_code,
            country=addr.country,
            address_type=addr_type,
            is_primary=is_primary,
            created_at=addr.created_at,
            updated_at=addr.updated_at
        )
        addresses_out.append(addr_out)

    # Get primary phone/email
    primary_phone = next(
        (i.identifier_value for i in identifiers if i.identifier_type == "phone"),
        None
    )
    primary_email = next(
        (i.identifier_value for i in identifiers if i.identifier_type == "email"),
        None
    )
    
    # Get organization info
    org_result = await db.execute(
        select(Organization)
        .join(Identifier, Identifier.organization_id == Organization.id)
        .where(Identifier.person_id == person_id)
        .limit(1)
    )
    organization = org_result.scalar_one_or_none()
    
    # Get call statistics
    call_count_result = await db.execute(
        select(func.count(Call.id)).where(Call.person_id == person_id)
    )
    call_count = call_count_result.scalar() or 0
    
    first_call_result = await db.execute(
        select(Call.created_at)
        .where(Call.person_id == person_id)
        .order_by(Call.created_at)
        .limit(1)
    )
    first_contact_at = first_call_result.scalar_one_or_none()
    
    last_call_result = await db.execute(
        select(Call.created_at)
        .where(Call.person_id == person_id)
        .order_by(desc(Call.created_at))
        .limit(1)
    )
    last_contact_at = last_call_result.scalar_one_or_none()
    
    # Get task statistics
    open_tasks_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.person_id == person_id,
            Task.status == "open"
        )
    )
    open_tasks_count = open_tasks_result.scalar() or 0
    
    total_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.person_id == person_id)
    )
    total_tasks_count = total_tasks_result.scalar() or 0
    
    # Get offers count (simplified for now - from calls)
    offers_count = 0  # TODO: implement when offers query is needed
    
    # Compute display label
    display_label = person.full_name or primary_phone or f"Customer #{person.id}"
    
    return PersonDetailsOut(
        id=person.id,
        full_name=person.full_name,
        given_name=person.given_name,
        family_name=person.family_name,
        display_label=display_label,
        date_of_birth=person.date_of_birth,
        id_number=person.id_number,
        identifiers=identifiers_out,
        primary_phone=primary_phone,
        primary_email=primary_email,
        addresses=addresses_out,
        organization_name=organization.name if organization else None,
        organization_id=organization.id if organization else None,
        call_count=call_count,
        open_tasks_count=open_tasks_count,
        total_tasks_count=total_tasks_count,
        offers_count=offers_count,
        first_contact_at=first_contact_at,
        last_contact_at=last_contact_at,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


async def _get_primary_identifier(
    db: AsyncSession,
    person_id: int,
    identifier_type: str
) -> Optional[str]:
    """Get primary identifier value for a person."""
    result = await db.execute(
        select(Identifier.identifier_value)
        .where(
            Identifier.person_id == person_id,
            Identifier.identifier_type == identifier_type
        )
        .order_by(Identifier.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()
