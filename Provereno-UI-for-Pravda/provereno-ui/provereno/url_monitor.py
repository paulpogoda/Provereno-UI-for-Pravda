"""Background URL availability monitor."""
from __future__ import annotations
import asyncio, logging
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select, update

from provereno.database import AsyncSessionLocal
from provereno.models import Snapshot, UrlCheck

log = logging.getLogger(__name__)
CHECK_INTERVAL = 3600  # seconds between full cycles


def _classify(status: int) -> str:
    if status == 0:
        return "unknown"
    if 200 <= status < 400:
        return "online"
    if status in (404, 410):
        return "deleted"
    if status in (401, 403):
        return "blocked"
    return "changed"


class UrlMonitor:
    _task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while True:
            try:
                await self._check_all()
            except Exception as exc:
                log.warning("UrlMonitor error: %s", exc)
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_all(self) -> None:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(Snapshot.id, Snapshot.url).where(Snapshot.url.isnot(None))
            )
            snapshots = rows.all()

        connector = aiohttp.TCPConnector(ssl=False, limit=10)
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as client:
            for snap_id, url in snapshots:
                await self._check_one(snap_id, url, client)
                await asyncio.sleep(0.5)

    async def _check_one(self, snap_id: str, url: str, client: aiohttp.ClientSession) -> None:
        try:
            async with client.head(url, allow_redirects=True) as resp:
                http_status = resp.status
        except Exception:
            http_status = 0

        status = _classify(http_status)
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as session:
            session.add(UrlCheck(
                snapshot_id=snap_id, status=status,
                http_status=http_status, checked_at=now,
            ))
            await session.execute(
                update(Snapshot)
                .where(Snapshot.id == snap_id)
                .values(url_status=status)
            )
            await session.commit()


url_monitor = UrlMonitor()
