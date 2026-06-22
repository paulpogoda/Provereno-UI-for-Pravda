"""Snapshot CRUD, tag management, list with filters."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import pathlib

from provereno.auth import require_auth
from provereno.database import get_db
from provereno.models import Snapshot, SnapshotTag, Tag

router = APIRouter()


@router.get("/snapshots", response_class=HTMLResponse)
async def list_snapshots(
    request: Request,
    q: str = "", tag: str = "",
    page: int = 1, per_page: int = 25,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_auth),
):
    query = select(Snapshot)
    if q:
        query = query.where(Snapshot.url.ilike(f"%{q}%"))
    if tag:
        query = query.join(SnapshotTag, Snapshot.id == SnapshotTag.snapshot_id
                           ).where(SnapshotTag.tag_name == tag)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    rows = await session.execute(
        query.order_by(Snapshot.captured_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    )
    snapshots = rows.scalars().all()

    all_tags = (await session.execute(select(Tag.name).order_by(Tag.name))).scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse("snapshots.html", {
        "request": request, "snapshots": snapshots, "total": total,
        "page": page, "pages": max(1, (total + per_page - 1) // per_page),
        "q": q, "tag": tag, "all_tags": all_tags, "user": user, "active": "snapshots",
    })


@router.get("/snapshots/{snapshot_id}", response_class=HTMLResponse)
async def view_snapshot(
    snapshot_id: str, request: Request,
    session: AsyncSession = Depends(get_db), user=Depends(require_auth),
):
    from fastapi import HTTPException
    snap = await session.get(Snapshot, snapshot_id)
    if not snap:
        raise HTTPException(404)
    rows = await session.execute(
        select(SnapshotTag.tag_name).where(SnapshotTag.snapshot_id == snapshot_id)
    )
    tags = [r[0] for r in rows.all()]
    all_tags = (await session.execute(select(Tag.name).order_by(Tag.name))).scalars().all()
    templates = request.app.state.templates
    return templates.TemplateResponse("snapshot_detail.html", {
        "request": request, "snap": snap, "tags": tags,
        "all_tags": all_tags, "user": user,
    })


@router.get("/snapshots/{snapshot_id}/screenshot")
async def snapshot_screenshot(snapshot_id: str,
                               session: AsyncSession = Depends(get_db),
                               user=Depends(require_auth)):
    from fastapi import HTTPException
    snap = await session.get(Snapshot, snapshot_id)
    if not snap or not snap.screenshot_path:
        raise HTTPException(404)
    data = pathlib.Path(snap.screenshot_path).read_bytes()
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/snapshots/{snapshot_id}/mhtml")
async def snapshot_mhtml(snapshot_id: str,
                         session: AsyncSession = Depends(get_db),
                         user=Depends(require_auth)):
    from fastapi import HTTPException
    snap = await session.get(Snapshot, snapshot_id)
    if not snap or not snap.mhtml_path:
        raise HTTPException(404)
    data = pathlib.Path(snap.mhtml_path).read_bytes()
    filename = f"snapshot-{snapshot_id[:8]}.mhtml"
    return Response(content=data, media_type="message/rfc822",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/snapshots/{snapshot_id}/tags")
async def add_tag(snapshot_id: str, request: Request,
                  session: AsyncSession = Depends(get_db), user=Depends(require_auth)):
    form = await request.form()
    tag_name = (form.get("tag_name") or "").strip()[:64]
    if tag_name:
        existing = await session.get(Tag, tag_name)
        if not existing:
            session.add(Tag(name=tag_name))
        st = await session.get(SnapshotTag, (snapshot_id, tag_name))
        if not st:
            session.add(SnapshotTag(snapshot_id=snapshot_id, tag_name=tag_name))
        await session.commit()
    return RedirectResponse(f"/snapshots/{snapshot_id}", status_code=303)


@router.post("/snapshots/{snapshot_id}/tags/{tag_name}/remove")
async def remove_tag(snapshot_id: str, tag_name: str,
                     session: AsyncSession = Depends(get_db), user=Depends(require_auth)):
    await session.execute(
        delete(SnapshotTag).where(
            SnapshotTag.snapshot_id == snapshot_id,
            SnapshotTag.tag_name == tag_name,
        )
    )
    await session.commit()
    return RedirectResponse(f"/snapshots/{snapshot_id}", status_code=303)


@router.post("/snapshots/{snapshot_id}/toggle-public")
async def toggle_public(snapshot_id: str,
                        session: AsyncSession = Depends(get_db), user=Depends(require_auth)):
    from fastapi import HTTPException
    snap = await session.get(Snapshot, snapshot_id)
    if not snap: raise HTTPException(404)
    snap.is_public = not snap.is_public
    await session.commit()
    return RedirectResponse(f"/snapshots/{snapshot_id}", status_code=303)


@router.post("/snapshots/{snapshot_id}/delete")
async def delete_snapshot(snapshot_id: str,
                           session: AsyncSession = Depends(get_db), user=Depends(require_auth)):
    from fastapi import HTTPException
    snap = await session.get(Snapshot, snapshot_id)
    if not snap: raise HTTPException(404)
    for path in [snap.mhtml_path, snap.screenshot_path]:
        if path:
            try: pathlib.Path(path).unlink(missing_ok=True)
            except Exception: pass
    await session.delete(snap)
    await session.commit()
    return RedirectResponse("/snapshots", status_code=303)
