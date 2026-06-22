"""Public evidence viewer — no auth required."""
from __future__ import annotations
import pathlib
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from provereno.database import get_db
from provereno.models import Snapshot

router = APIRouter(prefix="/public")


@router.get("/evidence/{snapshot_id}", response_class=HTMLResponse)
async def public_evidence(snapshot_id: str, request: Request,
                          session: AsyncSession = Depends(get_db)):
    snap = await session.get(Snapshot, snapshot_id)
    if not snap or not snap.is_public:
        raise HTTPException(404, "Evidence not found or not public")
    return request.app.state.templates.TemplateResponse(
        "public_evidence.html",
        {"request": request, "snap": snap},
    )


@router.get("/evidence/{snapshot_id}/screenshot")
async def public_screenshot(snapshot_id: str, session: AsyncSession = Depends(get_db)):
    snap = await session.get(Snapshot, snapshot_id)
    if not snap or not snap.is_public or not snap.screenshot_path:
        raise HTTPException(404)
    data = pathlib.Path(snap.screenshot_path).read_bytes()
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
