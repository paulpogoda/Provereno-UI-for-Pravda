"""Async job runner with SSE streaming."""
from __future__ import annotations
import asyncio, json, pathlib, uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from provereno.capture import capture_service
from provereno.config import settings
from provereno.database import AsyncSessionLocal
from provereno.models import Job, Snapshot, SnapshotTag, Tag


_queue: asyncio.Queue[str] = asyncio.Queue()
_subscribers: dict[str, list[asyncio.Queue]] = {}


def _utcnow():
    return datetime.now(timezone.utc)


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def subscribe(job_id: str) -> asyncio.Queue:
    q: asyncio.Queue[str] = asyncio.Queue()
    _subscribers.setdefault(job_id, []).append(q)
    return q


def unsubscribe(job_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(job_id, [])
    try:
        subs.remove(q)
    except ValueError:
        pass


def _publish(job_id: str, event: str, data: dict) -> None:
    msg = _sse(event, data)
    for q in list(_subscribers.get(job_id, [])):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def enqueue(
    url: str, condition_type: str = "load", condition: Optional[str] = None,
    note: Optional[str] = None, tags: Optional[list] = None,
    created_by: Optional[str] = None, batch_id: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        job = Job(
            id=job_id, batch_id=batch_id, url=url,
            condition_type=condition_type, condition=condition,
            note=note, tags=tags or [], created_by=created_by,
            status="queued", created_at=_utcnow(),
        )
        session.add(job)
        await session.commit()
    await _queue.put(job_id)
    return job_id


async def _run_job(job_id: str) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            return
        job.status = "capturing"
        job.started_at = _utcnow()
        await session.commit()

    _publish(job_id, "progress", {"status": "capturing", "message": "Browser launching..."})

    try:
        result = await capture_service.capture(
            url=job.url,
            condition_type=job.condition_type or "load",
            condition=job.condition,
        )
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            j = await session.get(Job, job_id)
            if j:
                j.status = "error"
                j.error_message = str(exc)[:500]
                j.finished_at = _utcnow()
                await session.commit()
        _publish(job_id, "error", {"status": "error", "message": str(exc)[:200]})
        return

    # Persist snapshot
    data_dir = pathlib.Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    snap_id = str(uuid.uuid4())

    mhtml_path = ""
    if result.mhtml:
        p = data_dir / f"{snap_id}.mhtml"
        p.write_bytes(result.mhtml)
        mhtml_path = str(p)

    shot_path = ""
    if result.screenshot_png:
        p = data_dir / f"{snap_id}.png"
        p.write_bytes(result.screenshot_png)
        shot_path = str(p)

    async with AsyncSessionLocal() as session:
        snap = Snapshot(
            id=snap_id, url=job.url,
            final_url=result.final_url, http_status=result.http_status,
            headers=result.headers, mhtml_path=mhtml_path,
            mhtml_sha256=result.mhtml_sha256,
            screenshot_path=shot_path,
            lifecycle_events=result.lifecycle_events,
            condition_type=job.condition_type, condition=job.condition,
            condition_met=result.condition_met,
            note=job.note, creator=job.created_by,
            captured_at=_utcnow(), job_id=job_id,
        )
        session.add(snap)

        # tags
        for tag_name in (job.tags or []):
            tag_name = tag_name.strip()[:64]
            if not tag_name:
                continue
            existing = await session.get(Tag, tag_name)
            if not existing:
                session.add(Tag(name=tag_name))
            session.add(SnapshotTag(snapshot_id=snap_id, tag_name=tag_name))

        job_row = await session.get(Job, job_id)
        if job_row:
            job_row.status = "done"
            job_row.snapshot_id = snap_id
            job_row.finished_at = _utcnow()

        await session.commit()

    _publish(job_id, "done", {
        "status": "done", "snapshot_id": snap_id,
        "redirect": f"/snapshots/{snap_id}",
    })


async def worker() -> None:
    """Background worker — processes jobs from queue one at a time."""
    while True:
        try:
            job_id = await asyncio.wait_for(_queue.get(), timeout=2.0)
            await _run_job(job_id)
        except asyncio.TimeoutError:
            continue
        except Exception:
            pass


async def sse_stream(job_id: str) -> AsyncGenerator[str, None]:
    q = subscribe(job_id)
    try:
        yield _sse("connected", {"job_id": job_id})
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=20.0)
                yield msg
                if '"done"' in msg or '"error"' in msg:
                    break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        unsubscribe(job_id, q)
