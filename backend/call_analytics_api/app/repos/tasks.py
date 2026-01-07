"""Repository layer for task-related database operations."""

from typing import List, Optional
from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from backend.common.models_db import Task, Person, Agent, Call
from backend.call_analytics_api.app.schemas_business import (
    TaskOut,
    TaskListItemOut,
    TaskUpdateIn,
)


async def list_tasks(
    db: AsyncSession,
    status: Optional[str] = None,
    person_id: Optional[int] = None,
    owner_agent_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> List[TaskListItemOut]:
    """List tasks with optional filtering - optimized for tasks list page."""
    
    # Base query with joins
    stmt = (
        select(Task)
        .options(
            joinedload(Task.person),
            joinedload(Task.owner_agent),
            joinedload(Task.call),
        )
        .order_by(desc(Task.created_at))
    )
    
    # Apply filters
    if status:
        stmt = stmt.where(Task.status == status)
    
    if person_id:
        stmt = stmt.where(Task.person_id == person_id)
    
    if owner_agent_id:
        stmt = stmt.where(Task.owner_agent_id == owner_agent_id)
    
    stmt = stmt.limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    # Build output
    output = []
    for task in tasks:
        person_name = None
        if task.person:
            person_name = task.person.full_name
        
        owner_agent_name = None
        if task.owner_agent:
            owner_agent_name = task.owner_agent.display_name or task.owner_agent.external_agent_id
        
        call_headline = None
        call_date = None
        if task.call:
            call_headline = task.call.headline
            call_date = task.call.created_at
        
        output.append(TaskListItemOut(
            id=task.id,
            call_id=task.call_id,
            title=task.title,
            status=task.status,
            due_at=task.due_at,
            person_name=person_name,
            owner_agent_name=owner_agent_name,
            call_headline=call_headline,
            call_date=call_date,
            created_at=task.created_at,
            updated_at=task.updated_at,
        ))
    
    return output


async def get_task_details(
    db: AsyncSession,
    task_id: int
) -> Optional[TaskOut]:
    """Get detailed task information."""
    
    # Fetch task with relationships
    task_result = await db.execute(
        select(Task)
        .options(
            joinedload(Task.person),
            joinedload(Task.owner_agent),
        )
        .where(Task.id == task_id)
    )
    task = task_result.scalar_one_or_none()
    
    if not task:
        return None
    
    # Build output
    person_name = None
    if task.person:
        person_name = task.person.full_name
    
    owner_agent_name = None
    if task.owner_agent:
        owner_agent_name = task.owner_agent.display_name or task.owner_agent.external_agent_id
    
    return TaskOut(
        id=task.id,
        call_id=task.call_id,
        title=task.title,
        description=task.description,
        status=task.status,
        due_at=task.due_at,
        owner_agent_id=task.owner_agent_id,
        owner_agent_name=owner_agent_name,
        person_id=task.person_id,
        person_name=person_name,
        organization_id=task.organization_id,
        extraction_id=task.extraction_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


async def update_task(
    db: AsyncSession,
    task_id: int,
    update_data: TaskUpdateIn
) -> Optional[TaskOut]:
    """Update task fields."""
    
    # Build update dict from non-None fields
    update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
    
    if not update_dict:
        # Nothing to update, just return current state
        return await get_task_details(db, task_id)
    
    # Perform update
    stmt = (
        update(Task)
        .where(Task.id == task_id)
        .values(**update_dict)
        .returning(Task.id)
    )
    
    result = await db.execute(stmt)
    updated_id = result.scalar_one_or_none()
    
    if not updated_id:
        return None
    
    await db.commit()
    
    # Return updated task
    return await get_task_details(db, task_id)


async def get_tasks_for_person(
    db: AsyncSession,
    person_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[TaskOut]:
    """Get tasks associated with a specific person."""
    
    stmt = (
        select(Task)
        .options(
            joinedload(Task.person),
            joinedload(Task.owner_agent),
        )
        .where(Task.person_id == person_id)
        .order_by(desc(Task.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    # Build output
    output = []
    for task in tasks:
        person_name = None
        if task.person:
            person_name = task.person.full_name
        
        owner_agent_name = None
        if task.owner_agent:
            owner_agent_name = task.owner_agent.display_name or task.owner_agent.external_agent_id
        
        output.append(TaskOut(
            id=task.id,
            call_id=task.call_id,
            title=task.title,
            description=task.description,
            status=task.status,
            due_at=task.due_at,
            owner_agent_id=task.owner_agent_id,
            owner_agent_name=owner_agent_name,
            person_id=task.person_id,
            person_name=person_name,
            organization_id=task.organization_id,
            extraction_id=task.extraction_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        ))
    
    return output


async def get_tasks_for_call(
    db: AsyncSession,
    call_id: int
) -> List[TaskOut]:
    """Get tasks associated with a specific call."""
    
    stmt = (
        select(Task)
        .options(
            joinedload(Task.person),
            joinedload(Task.owner_agent),
        )
        .where(Task.call_id == call_id)
        .order_by(Task.created_at)
    )
    
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    # Build output
    output = []
    for task in tasks:
        person_name = None
        if task.person:
            person_name = task.person.full_name
        
        owner_agent_name = None
        if task.owner_agent:
            owner_agent_name = task.owner_agent.display_name or task.owner_agent.external_agent_id
        
        output.append(TaskOut(
            id=task.id,
            call_id=task.call_id,
            title=task.title,
            description=task.description,
            status=task.status,
            due_at=task.due_at,
            owner_agent_id=task.owner_agent_id,
            owner_agent_name=owner_agent_name,
            person_id=task.person_id,
            person_name=person_name,
            organization_id=task.organization_id,
            extraction_id=task.extraction_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        ))
    
    return output
