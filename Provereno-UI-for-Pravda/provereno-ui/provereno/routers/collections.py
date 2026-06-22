"""Collections CRUD."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from provereno.auth import require_auth
from provereno.database import get_db
from provereno.models import Collection, CollectionSnapshot, Snapshot

router = APIRouter()


@router.get("/collections", response_class=HTMLResponse)
async def list_collections(request: Request, session: AsyncSession = Depends(get_db),
                           user=Depends(require_auth)):
    rows = await session.execute(
        select(Collection, func.count(CollectionSnapshot.snapshot_id).label("count"))
        .outerjoin(CollectionSnapshot, Collection.id == CollectionSnapshot.collection_id)
        .group_by(Collection.id).order_by(Collection.created_at.desc())
    )
    collections = [{"collection": r[0], "count": r[1]} for r in rows.all()]
    return request.app.state.templates.TemplateResponse(
        "collections.html",
        {"request": request, "collections": collections, "user": user, "active": "collections"},
    )


@router.post("/collections")
async def create_collection(request: Request, session: AsyncSession = Depends(get_db),
                            user=Depends(require_auth)):
    form = await request.form()
    name = (form.get("name") or "").strip()[:128]
    description = (form.get("description") or "").strip()[:512]
    if not name:
        return RedirectResponse("/collections", status_code=303)
    col = Collection(id=str(uuid.uuid4()), name=name,
                     description=description or None, created_by=user.github_login)
    session.add(col); await session.commit()
    return RedirectResponse(f"/collections/{col.id}", status_code=303)


@router.get("/collections/{collection_id}", response_class=HTMLResponse)
async def view_collection(collection_id: str, request: Request, page: int = 1,
                          session: AsyncSession = Depends(get_db), user=Depends(require_auth)):
    col = await session.get(Collection, collection_id)
    if not col: raise HTTPException(404)
    per_page = 25
    total = (await session.execute(
        select(func.count()).where(CollectionSnapshot.collection_id == collection_id)
    )).scalar() or 0
    snaps = (await session.execute(
        select(Snapshot).join(CollectionSnapshot, Snapshot.id == CollectionSnapshot.snapshot_id)
        .where(CollectionSnapshot.collection_id == collection_id)
        .order_by(Snapshot.captured_at.desc())
        .offset((page-1)*per_page).limit(per_page)
    )).scalars().all()
    all_snaps = (await session.execute(
        select(Snapshot).order_by(Snapshot.captured_at.desc()).limit(100)
    )).scalars().all()
    return request.app.state.templates.TemplateResponse("collection_detail.html", {
        "request": request, "collection": col, "snapshots": snaps,
        "all_snapshots": all_snaps, "total": total,
        "page": page, "pages": max(1, (total+per_page-1)//per_page),
        "user": user, "active": "collections",
    })


@router.post("/collections/{collection_id}/snapshots")
async def add_to_collection(collection_id: str, request: Request,
                            session: AsyncSession = Depends(get_db), user=Depends(require_auth)):
    form = await request.form()
    snap_id = (form.get("snapshot_id") or "").strip()
    existing = (await session.execute(
        select(CollectionSnapshot).where(
            CollectionSnapshot.collection_id == collection_id,
            CollectionSnapshot.snapshot_id == snap_id,
        )
    )).scalar_one_or_none()
    if not existing:
        session.add(CollectionSnapshot(collection_id=collection_id, snapshot_id=snap_id))
        await session.commit()
    return RedirectResponse(f"/collections/{collection_id}", status_code=303)


@router.post("/collections/{collection_id}/snapshots/{snapshot_id}/remove")
async def remove_from_collection(collection_id: str, snapshot_id: str,
                                 session: AsyncSession = Depends(get_db),
                                 user=Depends(require_auth)):
    row = (await session.execute(
        select(CollectionSnapshot).where(
            CollectionSnapshot.collection_id == collection_id,
            CollectionSnapshot.snapshot_id == snapshot_id,
        )
    )).scalar_one_or_none()
    if row: await session.delete(row); await session.commit()
    return RedirectResponse(f"/collections/{collection_id}", status_code=303)


@router.post("/collections/{collection_id}/delete")
async def delete_collection(collection_id: str, session: AsyncSession = Depends(get_db),
                            user=Depends(require_auth)):
    col = await session.get(Collection, collection_id)
    if col: await session.delete(col); await session.commit()
    return RedirectResponse("/collections", status_code=303)
