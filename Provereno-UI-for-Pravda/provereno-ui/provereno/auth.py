from __future__ import annotations
import secrets
from typing import Optional
from fastapi import HTTPException, Request
from sqlalchemy import select

_sessions: dict[str, str] = {}  # session_token -> github_login

def create_session(login: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = login
    return token

def get_session_login(request: Request) -> Optional[str]:
    token = request.cookies.get("session")
    return _sessions.get(token) if token else None

async def require_auth(request: Request):
    from provereno.database import AsyncSessionLocal
    from provereno.models import User
    login = get_session_login(request)
    if not login:
        from fastapi.responses import RedirectResponse
        raise HTTPException(status_code=307, headers={"Location": "/auth/login"})
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.github_login == login))
        user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    return user

async def require_admin(request: Request):
    user = await require_auth(request)
    if user.role != "admin":
        raise HTTPException(403, "Admin required")
    return user
