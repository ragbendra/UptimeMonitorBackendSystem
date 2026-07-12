from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db import get_db_session
from app.models import Monitor, User
from app.models.enums import MonitorMethod
from app.schemas.monitor import (
    MonitorCreateRequest,
    MonitorResponse,
    MonitorUpdateRequest,
)


router = APIRouter(prefix="/monitors", tags=["monitors"])


async def get_owned_monitor(
    monitor_id: int,
    current_user: User,
    session: AsyncSession,
) -> Monitor:
    monitor = await session.scalar(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == current_user.id,
        )
    )
    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor was not found.",
        )
    return monitor


@router.post(
    "",
    response_model=MonitorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_monitor(
    payload: MonitorCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Monitor:
    monitor = Monitor(
        user_id=current_user.id,
        name=payload.name,
        target_url=str(payload.target_url),
        method=MonitorMethod.GET,
        check_interval_seconds=payload.check_interval_seconds,
    )

    session.add(monitor)
    await session.commit()
    await session.refresh(monitor)
    return monitor


@router.get("", response_model=list[MonitorResponse])
async def list_monitors(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[Monitor]:
    result = await session.execute(
        select(Monitor)
        .where(Monitor.user_id == current_user.id)
        .order_by(Monitor.created_at.desc(), Monitor.id.desc())
    )
    return list(result.scalars().all())


@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(
    monitor_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Monitor:
    return await get_owned_monitor(monitor_id, current_user, session)


@router.patch("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(
    monitor_id: int,
    payload: MonitorUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Monitor:
    monitor = await get_owned_monitor(monitor_id, current_user, session)
    changes = payload.model_dump(exclude_unset=True)

    if "target_url" in changes:
        changes["target_url"] = str(changes["target_url"])

    for field, value in changes.items():
        setattr(monitor, field, value)

    await session.commit()
    await session.refresh(monitor)
    return monitor


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    monitor = await get_owned_monitor(monitor_id, current_user, session)

    await session.delete(monitor)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
