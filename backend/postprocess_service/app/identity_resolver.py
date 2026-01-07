"""Identity resolution helpers for postprocess service."""

import logging
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.models_db import Agent, Person, Organization, Identifier, Call

logger = logging.getLogger(__name__)


async def resolve_or_create_agent(
    session: AsyncSession,
    external_agent_id: str,
) -> Optional[Agent]:
    """Resolve or create an agent by external_agent_id."""
    if not external_agent_id:
        return None

    result = await session.execute(
        select(Agent).where(Agent.external_agent_id == external_agent_id)
    )
    agent = result.scalar_one_or_none()

    if agent is None:
        agent = Agent(external_agent_id=external_agent_id)
        session.add(agent)
        await session.flush()
        logger.info("Created new agent: %s", external_agent_id)

    return agent


async def resolve_or_create_person_org(
    session: AsyncSession,
    phones: list[str],
    emails: list[str],
    person_names: list[str],
    company_names: list[str],
) -> Tuple[Optional[Person], Optional[Organization]]:
    """
    Resolve or create person/organization via identifiers (phone/email).
    Returns (person, organization) tuple.
    """
    person: Optional[Person] = None
    organization: Optional[Organization] = None

    # Try to resolve by phone first
    for phone in phones:
        if not phone:
            continue
        result = await session.execute(
            select(Identifier).where(
                Identifier.identifier_type == "phone",
                Identifier.normalized_value == phone,
            )
        )
        ident = result.scalar_one_or_none()
        if ident is not None:
            person = ident.person
            organization = ident.organization
            logger.info("Resolved person/org by phone: %s", phone)
            break

    # Fall back to email
    if person is None and emails:
        for email in emails:
            if not email:
                continue
            result = await session.execute(
                select(Identifier).where(
                    Identifier.identifier_type == "email",
                    Identifier.normalized_value == email,
                )
            )
            ident = result.scalar_one_or_none()
            if ident is not None:
                person = ident.person
                organization = ident.organization
                logger.info("Resolved person/org by email: %s", email)
                break

    # If still unresolved, create new person (and optional org)
    if person is None and (phones or emails):
        full_name = person_names[0] if person_names else None
        person = Person(full_name=full_name)
        session.add(person)
        await session.flush()
        logger.info("Created new person: %s", full_name)

        if company_names:
            org_name = company_names[0]
            org_result = await session.execute(
                select(Organization).where(Organization.name == org_name)
            )
            organization = org_result.scalar_one_or_none()
            if organization is None:
                organization = Organization(name=org_name)
                session.add(organization)
                await session.flush()
                logger.info("Created new organization: %s", org_name)

        # Create identifiers for newly created person/org
        for phone in phones:
            if phone:
                # Check if identifier already exists (race condition safety)
                existing_ident_result = await session.execute(
                    select(Identifier).where(
                        Identifier.identifier_type == "phone",
                        Identifier.normalized_value == phone,
                    )
                )
                existing_ident = existing_ident_result.scalar_one_or_none()
                if existing_ident is None:
                    session.add(
                        Identifier(
                            identifier_type="phone",
                            identifier_value=phone,
                            normalized_value=phone,
                            person_id=person.id,
                            organization_id=organization.id if organization else None,
                        )
                    )
        for email in emails:
            if email:
                # Check if identifier already exists (race condition safety)
                existing_ident_result = await session.execute(
                    select(Identifier).where(
                        Identifier.identifier_type == "email",
                        Identifier.normalized_value == email,
                    )
                )
                existing_ident = existing_ident_result.scalar_one_or_none()
                if existing_ident is None:
                    session.add(
                        Identifier(
                            identifier_type="email",
                            identifier_value=email,
                            normalized_value=email,
                            person_id=person.id,
                            organization_id=organization.id if organization else None,
                        )
                    )
    
    # Update person statistics if person exists
    if person:
        await update_person_stats(session, person.id)

    return person, organization


async def update_person_stats(session: AsyncSession, person_id: int) -> None:
    """
    Update person statistics based on linked calls.
    Called after linking a call to a person.
    """
    # Count calls linked to this person
    call_count_result = await session.execute(
        select(func.count(Call.id)).where(Call.person_id == person_id)
    )
    call_count = call_count_result.scalar() or 0
    
    # Get first and last call dates
    first_call_result = await session.execute(
        select(Call.created_at)
        .where(Call.person_id == person_id)
        .order_by(Call.created_at)
        .limit(1)
    )
    first_call_date = first_call_result.scalar_one_or_none()
    
    last_call_result = await session.execute(
        select(Call.created_at)
        .where(Call.person_id == person_id)
        .order_by(Call.created_at.desc())
        .limit(1)
    )
    last_call_date = last_call_result.scalar_one_or_none()
    
    # Update person record (requires adding fields to Person model first)
    # For now, just log - we'll add fields to model next
    logger.info(
        "Person %s stats: %d calls, first: %s, last: %s",
        person_id, call_count, first_call_date, last_call_date
    )
