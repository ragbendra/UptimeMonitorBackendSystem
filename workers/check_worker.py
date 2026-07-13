import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models import AlertJob, CheckJob, Incident, Monitor
from app.models.enums import AlertType, JobStatus


logger = logging.getLogger(__name__)

BATCH_SIZE = 5
CHECK_TIMEOUT_SECONDS = 10
WORKER_POLL_SECONDS = 3


async def claim_jobs(worker_id: str, batch_size: int = BATCH_SIZE) -> list[int]:
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CheckJob)
            .where(
                CheckJob.status == JobStatus.pending,
                or_(
                    CheckJob.next_attempt_at.is_(None),
                    CheckJob.next_attempt_at <= now,
                ),
            )
            .order_by(CheckJob.scheduled_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        jobs = list(result.scalars().all())

        for job in jobs:
            job.status = JobStatus.processing
            job.locked_by = worker_id
            job.locked_at = now

        await session.commit()
        return [job.id for job in jobs]


async def check_url(method: str, target_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS) as client:
            response = await client.request(method, target_url)
    except httpx.RequestError:
        return False

    return 200 <= response.status_code < 400


async def finish_check_job(job_id: int, is_up: bool) -> None:
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        job = await session.get(CheckJob, job_id)
        if job is None:
            return

        monitor = await session.get(Monitor, job.monitor_id)
        if monitor is None:
            job.status = JobStatus.done
            await session.commit()
            return

        job.status = JobStatus.done
        job.locked_by = None
        job.locked_at = None
        job.next_attempt_at = None
        monitor.last_checked_at = now

        if is_up:
            monitor.consecutive_failures = 0
            await resolve_incident_if_needed(session, monitor, now)
        else:
            monitor.consecutive_failures += 1
            await open_incident_if_needed(session, monitor, now)

        await session.commit()


async def open_incident_if_needed(
    session: AsyncSession,
    monitor: Monitor,
    now: datetime,
) -> None:
    if monitor.consecutive_failures != monitor.consecutive_failure_threshold:
        return

    existing_incident = await session.scalar(
        select(Incident).where(
            Incident.monitor_id == monitor.id,
            Incident.resolved_at.is_(None),
        )
    )
    if existing_incident is not None:
        return

    try:
        async with session.begin_nested():
            incident = Incident(monitor_id=monitor.id, started_at=now)
            session.add(incident)
            await session.flush()

            session.add(
                AlertJob(
                    incident_id=incident.id,
                    alert_type=AlertType.down,
                    status=JobStatus.pending,
                    idempotency_key=f"{incident.id}:down",
                )
            )
    except IntegrityError:
        return


async def resolve_incident_if_needed(
    session: AsyncSession,
    monitor: Monitor,
    now: datetime,
) -> None:
    incident = await session.scalar(
        select(Incident).where(
            Incident.monitor_id == monitor.id,
            Incident.resolved_at.is_(None),
        )
    )
    if incident is None:
        return

    incident.resolved_at = now
    session.add(
        AlertJob(
            incident_id=incident.id,
            alert_type=AlertType.recovery,
            status=JobStatus.pending,
            idempotency_key=f"{incident.id}:recovery",
        )
    )


async def retry_check_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(CheckJob, job_id)
        if job is None:
            return

        job.attempts += 1
        job.locked_by = None
        job.locked_at = None

        if job.attempts >= job.max_attempts:
            job.status = JobStatus.dead
        else:
            job.status = JobStatus.pending
            job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=2**job.attempts)

        await session.commit()


async def process_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(CheckJob, job_id)
        if job is None:
            return

        monitor = await session.get(Monitor, job.monitor_id)
        if monitor is None:
            job.status = JobStatus.done
            await session.commit()
            return

        method = monitor.method.value
        target_url = monitor.target_url

    is_up = await check_url(method, target_url)
    await finish_check_job(job_id, is_up)


async def run_check_worker() -> None:
    logging.basicConfig(level=logging.INFO)
    worker_id = str(uuid4())

    while True:
        job_ids = await claim_jobs(worker_id)
        if not job_ids:
            await asyncio.sleep(WORKER_POLL_SECONDS)
            continue

        for job_id in job_ids:
            try:
                await process_job(job_id)
            except Exception:
                logger.exception("Check job %s failed.", job_id)
                await retry_check_job(job_id)


if __name__ == "__main__":
    asyncio.run(run_check_worker())
