"""Misc HTML pages: dashboard, audit log."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from provereno.auth import require_auth, require_admin
from provereno.database import get_db
from provereno.models import Snapshot, Job, AuditLog

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_db),
                    user=Depends(require_auth)):
    total_snaps = (await session.execute(select(func.count(Snapshot.id)))).scalar() or 0
    recent = (await session.execute(
        select(Snapshot).order_by(Snapshot.captured_at.desc()).limit(10)
    )).scalars().all()
    active_jobs = (await session.execute(
        select(func.count(Job.id)).where(Job.status.in_(["queued", "capturing"]))
    )).scalar() or 0
    return request.app.state.templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, "total_snaps": total_snaps,
        "recent": recent, "active_jobs": active_jobs, "active": "dashboard",
    })


@router.get("/audit", response_class=HTMLResponse)
async def audit_log(request: Request, page: int = 1,
                    session: AsyncSession = Depends(get_db),
                    user=Depends(require_admin)):
    per_page = 50
    total = (await session.execute(select(func.count(AuditLog.id)))).scalar() or 0
    rows = (await session.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at))
        .offset((page-1)*per_page).limit(per_page)
    )).scalars().all()
    return request.app.state.templates.TemplateResponse("audit.html", {
        "request": request, "user": user, "logs": rows, "total": total,
        "page": page, "pages": max(1, (total+per_page-1)//per_page), "active": "audit",
    })

@router.get("/audit/export-csv")
async def audit_csv(session: AsyncSession = Depends(get_db),
                    user=Depends(require_admin)):
    import csv, io
    from fastapi.responses import StreamingResponse
    rows = (await session.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(10000)
    )).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at", "event_type", "actor", "object_id", "ip", "detail"])
    for r in rows:
        writer.writerow([r.created_at, r.event_type, r.actor or "",
                         r.object_id or "", r.ip or "", r.detail or ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )
