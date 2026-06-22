"""Forensic ZIP export."""
from __future__ import annotations
import pathlib
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from provereno.auth import require_auth
from provereno.database import get_db
from provereno.forensic import build_forensic_zip
from provereno.models import Snapshot, SnapshotTag

router = APIRouter()


@router.get("/snapshots/{snapshot_id}/export")
async def export_snapshot(
    snapshot_id: str,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_auth),
):
    from fastapi import HTTPException
    snap = await session.get(Snapshot, snapshot_id)
    if not snap:
        raise HTTPException(404, "Snapshot not found")

    mhtml = b""
    if snap.mhtml_path:
        try:
            mhtml = pathlib.Path(snap.mhtml_path).read_bytes()
        except OSError:
            pass

    screenshot_png = b""
    if snap.screenshot_path:
        try:
            screenshot_png = pathlib.Path(snap.screenshot_path).read_bytes()
        except OSError:
            pass

    rows = await session.execute(
        select(SnapshotTag.tag_name).where(SnapshotTag.snapshot_id == snapshot_id)
    )
    tags = [r[0] for r in rows.all()]

    zip_bytes = build_forensic_zip(
        snapshot_id=snap.id,
        url=snap.url,
        final_url=snap.final_url or snap.url,
        http_status=snap.http_status or 0,
        headers=snap.headers or {},
        mhtml=mhtml,
        mhtml_sha256=snap.mhtml_sha256 or "",
        screenshot_png=screenshot_png,
        lifecycle_events=snap.lifecycle_events or [],
        condition_type=snap.condition_type or "load",
        condition=snap.condition,
        condition_met=snap.condition_met or False,
        captured_at=snap.captured_at,
        creator=snap.creator,
        tags=tags,
        note=snap.note,
    )

    filename = f"evidence-{snapshot_id[:8]}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
