"""GitHub OAuth router."""
from __future__ import annotations
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx

from provereno.config import settings
from provereno.database import AsyncSessionLocal
from provereno.models import User
from sqlalchemy import select

router = APIRouter(prefix="/auth")
_state_store: dict[str, bool] = {}
GITHUB_AUTH  = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_API   = "https://api.github.com"


@router.get("/login")
async def login(request: Request, error: str = ""):
    state = secrets.token_urlsafe(16)
    _state_store[state] = True
    params = (f"client_id={settings.github_client_id}"
              f"&scope=read:org&state={state}")
    return request.app.state.templates.TemplateResponse(
        "login.html", {"request": request, "error": error or None}
    )


@router.get("/callback")
async def callback(code: str = "", state: str = ""):
    if state not in _state_store:
        return RedirectResponse("/auth/login?error=Доступ+запрещён.+Обратитесь+к+администратору.")
    _state_store.pop(state, None)

    async with httpx.AsyncClient() as client:
        tr = await client.post(
            GITHUB_TOKEN,
            data={"client_id": settings.github_client_id,
                  "client_secret": settings.github_client_secret,
                  "code": code},
            headers={"Accept": "application/json"}, timeout=10,
        )
        token_data = tr.json()
        access_token = token_data.get("access_token", "")
        if not access_token:
            return RedirectResponse("/auth/error")

        ur = await client.get(
            f"{GITHUB_API}/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=10,
        )
        gh_user = ur.json()
        gh_id    = gh_user.get("id")
        gh_login = gh_user.get("login", "")

    # Org/login restriction
    allowed_logins = [x.strip() for x in settings.allowed_github_logins.split(",") if x.strip()]
    allowed_orgs   = [x.strip() for x in settings.allowed_github_orgs.split(",")   if x.strip()]

    if allowed_logins and gh_login not in allowed_logins:
        if allowed_orgs:
            async with httpx.AsyncClient() as client:
                or_ = await client.get(
                    f"{GITHUB_API}/user/orgs",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                user_orgs = [o["login"] for o in or_.json()]
            if not any(org in allowed_orgs for org in user_orgs):
                return RedirectResponse("/auth/denied")
        else:
            return RedirectResponse("/auth/denied")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.github_id == gh_id))
        user = result.scalar_one_or_none()
        if user:
            user.last_login_at = datetime.now(timezone.utc)
        else:
            user = User(github_id=gh_id, github_login=gh_login, role="editor",
                        last_login_at=datetime.now(timezone.utc))
            session.add(user)
        await session.commit()

    from provereno.auth import create_session
    session_token = create_session(gh_login)
    resp = RedirectResponse("/")
    resp.set_cookie("session", session_token, httponly=True, samesite="lax", max_age=86400*30)
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse("/auth/login")
    resp.delete_cookie("session")
    return resp


@router.get("/denied", response_class=HTMLResponse)
async def denied():
    return HTMLResponse("<h1>Access denied</h1><p>Your GitHub account is not authorized.</p>", 403)

@router.get("/error", response_class=HTMLResponse)
async def error():
    return HTMLResponse("<h1>Auth error</h1><p>OAuth flow failed.</p>", 500)