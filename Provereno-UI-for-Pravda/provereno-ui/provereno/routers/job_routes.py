"""Job submission, SSE stream, bulk CSV import."""
from __future__ import annotations
import csv, io, uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from provereno.auth import require_auth
from provereno.database import get_db
from provereno.models import Job
from provereno import jobs as job_module

router = APIRouter()


@router.post("/jobs")
async def create_job(request: Request, user=Depends(require_auth)):
    form = await request.form()
    url  = (form.get("url") or "").strip()
    if not url:
        return RedirectResponse("/", status_code=303)
    job_id = await job_module.enqueue(
        url=url,
        condition_type=(form.get("condition_type") or "load").strip(),
        condition=(form.get("condition") or "").strip() or None,
        note=(form.get("note") or "").strip() or None,
        tags=[t.strip() for t in (form.get("tags") or "").split(",") if t.strip()],
        created_by=user.github_login,
    )
    return RedirectResponse(f"/jobs/{job_id}/wait", status_code=303)


@router.get("/jobs/{job_id}/wait", response_class=HTMLResponse)
async def job_wait(job_id: str, request: Request,
                   session: AsyncSession = Depends(get_db),
                   user=Depends(require_auth)):
    job = await session.get(Job, job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "job_wait.html",
        {"request": request, "job": job, "user": user},
    )


@router.get("/jobs/{job_id}/stream")
async def job_stream(job_id: str, user=Depends(require_auth)):
    return StreamingResponse(
        job_module.sse_stream(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str,
                     session: AsyncSession = Depends(get_db),
                     user=Depends(require_auth)):
    job = await session.get(Job, job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404)
    return {"status": job.status, "snapshot_id": job.snapshot_id,
            "error": job.error_message}


# ── Bulk CSV import ────────────────────────────────────────────────────────
@router.get("/bulk", response_class=HTMLResponse)
async def bulk_page(request: Request, user=Depends(require_auth)):
    templates = request.app.state.templates
    return templates.TemplateResponse("bulk.html", {"request": request, "user": user})


@router.post("/bulk")
async def bulk_submit(request: Request, user=Depends(require_auth)):
    form = await request.form()
    upload = form.get("csvfile")
    raw_text = form.get("csv_text") or ""

    if upload and hasattr(upload, "read"):
        content = (await upload.read()).decode("utf-8", errors="replace")
    else:
        content = raw_text

    lines = []
    try:
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            url = (row.get("url") or row.get("URL") or "").strip()
            if url:
                lines.append({
                    "url": url,
                    "note": (row.get("note") or "").strip() or None,
                    "tags": [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()],
                })
    except Exception:
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append({"url": line, "note": None, "tags": []})

    lines = lines[:500]
    batch_id = str(uuid.uuid4())
    job_ids = []
    for item in lines:
        jid = await job_module.enqueue(
            url=item["url"], note=item["note"],
            tags=item["tags"], created_by=user.github_login,
            batch_id=batch_id,
        )
        job_ids.append(jid)

    return RedirectResponse(f"/bulk/{batch_id}", status_code=303)


@router.get("/bulk/{batch_id}", response_class=HTMLResponse)
async def bulk_progress(batch_id: str, request: Request,
                        session: AsyncSession = Depends(get_db),
                        user=Depends(require_auth)):
    rows = await session.execute(
        select(Job).where(Job.batch_id == batch_id).order_by(Job.created_at)
    )
    jobs = rows.scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "bulk_progress.html",
        {"request": request, "jobs": jobs, "batch_id": batch_id, "user": user},
    )


@router.get("/bulk/{batch_id}/status")
async def bulk_status(batch_id: str,
                      session: AsyncSession = Depends(get_db),
                      user=Depends(require_auth)):
    rows = await session.execute(
        select(Job.id, Job.url, Job.status, Job.snapshot_id, Job.error_message)
        .where(Job.batch_id == batch_id)
    )
    jobs = [{"id": r[0], "url": r[1], "status": r[2],
             "snapshot_id": r[3], "error": r[4]} for r in rows.all()]
    done = sum(1 for j in jobs if j["status"] in ("done", "error"))
    return {"total": len(jobs), "done": done, "jobs": jobs}
