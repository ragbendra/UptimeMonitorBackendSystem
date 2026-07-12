import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db import AsyncSessionLocal
from app.models import CheckJob, Monitor
from app.models.enums import JobStatus, MonitorStatus


logger = logging.getLogger(__name__)

SCHEDULER_LOCK_KEY = "scheduler:lock"
SCHEDULER_LOCK_TTL_SECONDS = 15


def is_monitor_due(monitor: Monitor, now: datetime) -> bool:
    if monitor.last_checked_at is None:
        return True
    return monitor.last_checked_at + timedelta(seconds=monitor.check_interval_seconds) <= now


def make_idempotency_key(monitor: Monitor, now: datetime) -> str:
    bucket = int(now.timestamp() // monitor.check_interval_seconds)
    return f"{monitor.id}:{bucket}"


async def enqueue_due_checks(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Monitor).where(Monitor.status == MonitorStatus.active)
        )
        due_monitors = [
            monitor for monitor in result.scalars().all() if is_monitor_due(monitor, now)
        ]

        for monitor in due_monitors:
            statement = (
                insert(CheckJob)
                .values(
                    monitor_id=monitor.id,
                    scheduled_at=now,
                    status=JobStatus.pending,
                    idempotency_key=make_idempotency_key(monitor, now),
                )
                .on_conflict_do_nothing(index_elements=[CheckJob.idempotency_key])
            )
            await session.execute(statement)

        await session.commit()
        return len(due_monitors)


async def release_lock(redis: Redis, instance_id: str) -> None:
    await redis.eval(
        """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        end
        return 0
        """,
        1,
        SCHEDULER_LOCK_KEY,
        instance_id,
    )


async def scheduler_tick(redis: Redis, instance_id: str) -> int:
    lock_acquired = await redis.set(
        SCHEDULER_LOCK_KEY,
        instance_id,
        nx=True,
        ex=SCHEDULER_LOCK_TTL_SECONDS,
    )
    if not lock_acquired:
        return 0

    try:
        return await enqueue_due_checks()
    finally:
        await release_lock(redis, instance_id)


async def run_scheduler() -> None:
    logging.basicConfig(level=logging.INFO)
    instance_id = str(uuid4())
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    try:
        while True:
            try:
                created = await scheduler_tick(redis, instance_id)
                if created:
                    logger.info("Enqueued %s check job(s).", created)
            except Exception:
                logger.exception("Scheduler tick failed.")

            await asyncio.sleep(settings.scheduler_poll_interval)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
