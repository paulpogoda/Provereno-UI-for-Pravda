"""FastAPI application factory."""
from __future__ import annotations
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from provereno.capture import capture_service
from provereno.database import engine
from provereno.models import Base
from provereno.url_monitor import url_monitor
from provereno import jobs as job_module

from provereno.routers import auth, snapshots, job_routes, export, collections, public, pages


def _datetimefmt(dt) -> str:
    if dt is None: return "—"
    try: return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception: return str(dt)

def _datetimeshort(dt) -> str:
    if dt is None: return "—"
    try: return dt.strftime("%d.%m %H:%M")
    except Exception: return str(dt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await capture_service.startup()
    await url_monitor.start()
    _worker_task = asyncio.create_task(job_module.worker())
    yield
    _worker_task.cancel()
    await url_monitor.stop()
    await capture_service.shutdown()
    await engine.dispose()


app = FastAPI(title="Provereno UI", lifespan=lifespan)

templates = Jinja2Templates(directory="provereno/templates")
templates.env.filters["datetimefmt"]   = _datetimefmt
templates.env.filters["datetimeshort"] = _datetimeshort
app.state.templates = templates

app.mount("/static", StaticFiles(directory="provereno/static"), name="static")

app.include_router(auth.router)
app.include_router(job_routes.router)
app.include_router(snapshots.router)
app.include_router(export.router)
app.include_router(collections.router)
app.include_router(public.router)
app.include_router(pages.router)
