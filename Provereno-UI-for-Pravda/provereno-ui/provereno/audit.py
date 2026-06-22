from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from provereno.models import AuditLog

async def log_event(
    session: AsyncSession, event: str,
    user_login: Optional[str] = None, ip: Optional[str] = None,
    resource_type: Optional[str] = None, resource_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    session.add(AuditLog(
        event=event, user_github_login=user_login, ip=ip,
        resource_type=resource_type, resource_id=resource_id,
        metadata_=metadata, created_at=datetime.now(timezone.utc),
    ))
    await session.flush()
