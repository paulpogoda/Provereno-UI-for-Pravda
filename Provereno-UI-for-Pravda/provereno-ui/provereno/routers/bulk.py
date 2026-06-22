"""Bulk CSV import router."""
from __future__ import annotations
import csv, io, json, uuid
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from provereno.auth import require_auth
from provereno.database import get_db
from provereno.models import Job
from provereno.jobs import enqueue_job

router = APIRouter()


def _parse_urls(text: str) -> list[str]:
    urls = []
    for line in text.splitlines():
        url = line.split(",")[0].strip().strip("'\"")
        if url.startswith("http://") or url.startswith("https://"):
            urls.append(url)
        if len(urls) >= 500:
            break
    return urls


@router.get("/bulk", response_class=HTMLResponse)
async def bulk_page(request: Request, session: AsyncSession = Depends(get_db),
                    user=Depends(require_auth)):
    # Recent batches summary
    rows = (await session.execute(
        select(
            Job.batch_id,
            func.count(Job.id).label("total"),
            func.sum((Job.status == "done").cast(int)).label("done"),
            func.sum((Job.status == "error").cast(int)).label("errors"),
            func.min(Job.created_at).label("created_at"),
        )
        .where(Job.batch_id.isnot(None))
        .group_by(Job.batch_id)
        .order_by(func.min(Job.created_at).desc())
        .limit(10)
    )).all()
    batches = [dict(r._mapping) for r in rows]
    return request.app.state.templates.TemplateResponse("bulk.html", {
        "request": request, "user": user, "active": "bulk", "batches": batches,
    })


@router.post("/bulk/submit")
async def bulk_submit(
    request: Request,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_auth),
    csv_file: UploadFile | None = File(None),
):
    form = await request.form()
    condition_type = str(form.get("condition_type", "load"))
    raw_tags = str(form.get("tags", ""))
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    paste = str(form.get("paste_urls", "") or "")
    if paste.strip():
        urls = _parse_urls(paste)
    elif csv_file and csv_file.filename:
        raw = (await csv_file.read()).decode("utf-8", errors="replace")
        urls = _parse_urls(raw)
    else:
        return RedirectResponse("/bulk", status_code=303)

    if not urls:
        return RedirectResponse("/bulk", status_code=303)

    batch_id = str(uuid.uuid4())
    for url in urls:
        await enqueue_job(
            session=session,
            url=url,
            condition_type=condition_type,
            creator=user.github_login,
            tags=tags,
            batch_id=batch_id,
        )

    return RedirectResponse(f"/bulk/{batch_id}", status_code=303)


@router.get("/bulk/{batch_id}", response_class=HTMLResponse)
async def batch_detail(batch_id: str, request: Request,
                       session: AsyncSession = Depends(get_db),
                       user=Depends(require_auth)):
    jobs = (await session.execute(
        select(Job).where(Job.batch_id == batch_id).order_by(Job.created_at)
    )).scalars().all()
    total = len(jobs)
    done = sum(1 for j in jobs if j.status == "done")
    errors = sum(1 for j in jobs if j.status == "error")
    running = any(j.status in ("queued", "capturing") for j in jobs)
    jobs_json = json.dumps([{
        "id": j.id, "url": j.url, "status": j.status,
        "http_status": j.http_status, "snapshot_id": j.snapshot_id,
        "error_message": j.error_message,
    } for j in jobs[:50]])
    return request.app.state.templates.TemplateResponse("bulk_progress.html", {
        "request": request, "user": user, "active": "bulk",
        "batch_id": batch_id, "total": total, "done": done,
        "errors": errors, "running": running, "jobs_json": jobs_json,
        "tag": "",
    })


@router.get("/bulk/{batch_id}/status")
async def batch_status(batch_id: str, session: AsyncSession = Depends(get_db),
                       user=Depends(require_auth)):
    from fastapi.responses import JSONResponse
    jobs = (await session.execute(
        select(Job).where(Job.batch_id == batch_id)
    )).scalars().all()
    return JSONResponse({
        "done": sum(1 for j in jobs if j.status == "done"),
        "errors": sum(1 for j in jobs if j.status == "error"),
        "running": any(j.status in ("queued", "capturing") for j in jobs),
        "jobs": [{
            "id": j.id, "url": j.url, "status": j.status,
            "http_status": j.http_status, "snapshot_id": j.snapshot_id,
            "error_message": j.error_message,
        } for j in jobs[:50]],
    })


@router.get("/bulk/{batch_id}/stream")
async def batch_stream(batch_id: str, session: AsyncSession = Depends(get_db),
                       user=Depends(require_auth)):
    import asyncio

    async def gen():
        import json as _json
        yield "event: connected\ndata: {}\n\n"
        seen_statuses: dict[str, str] = {}
        for _ in range(600):  # max 10 min
            await asyncio.sleep(1)
            jobs = (await session.execute(
                select(Job).where(Job.batch_id == batch_id)
            )).scalars().all()
            done = sum(1 for j in jobs if j.status == "done")
            errors = sum(1 for j in jobs if j.status == "error")
            running = any(j.status in ("queued", "capturing") for j in jobs)
            changed_job = None
            for j in jobs:
                if seen_statuses.get(j.id) != j.status:
                    seen_statuses[j.id] = j.status
                    changed_job = {
                        "id": j.id, "url": j.url, "status": j.status,
                        "http_status": j.http_status, "snapshot_id": j.snapshot_id,
                        "error_message": j.error_message,
                    }
            payload = _json.dumps({"done": done, "errors": errors,
                                   "running": running, "job": changed_job})
            yield f"event: progress\ndata: {payload}\n\n"
            if not running:
                yield "event: done\ndata: {}\n\n"
                break

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
