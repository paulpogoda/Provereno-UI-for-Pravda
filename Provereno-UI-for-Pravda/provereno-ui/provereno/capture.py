from __future__ import annotations
import asyncio, hashlib, time
from dataclasses import dataclass
from typing import Optional
from playwright.async_api import Browser, Playwright, Response, async_playwright


@dataclass
class CaptureResult:
    url: str
    final_url: str
    http_status: int
    headers: dict
    mhtml: bytes
    mhtml_sha256: str
    screenshot_png: bytes
    lifecycle_events: list
    condition_met: bool
    error: Optional[str] = None


class CaptureService:
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None

    async def startup(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            args=["--disable-dev-shm-usage", "--no-sandbox",
                  "--disable-setuid-sandbox", "--disable-gpu"]
        )

    async def shutdown(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def capture(self, url: str, condition_type: str = "load",
                      condition: Optional[str] = None,
                      timeout_ms: int = 60_000) -> CaptureResult:
        if not self._browser:
            raise RuntimeError("CaptureService not started")

        lifecycle: list[str] = []
        t0 = time.monotonic()

        def ms() -> int:
            return round((time.monotonic() - t0) * 1000)

        ctx = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "Chrome/124.0 Safari/537.36"
            ),
            java_script_enabled=True,
            ignore_https_errors=False,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = await ctx.new_page()
        http_status, resp_headers, final_url = 0, {}, url

        async def on_response(resp: Response) -> None:
            nonlocal http_status, resp_headers, final_url
            if resp.request.is_navigation_request():
                http_status = resp.status
                resp_headers = dict(resp.headers)
                final_url = resp.url
                lifecycle.append(f"{ms()}ms  HTTP {resp.status} <- {resp.url}")

        page.on("response", on_response)
        page.on("domcontentloaded", lambda: lifecycle.append(f"{ms()}ms  DOMContentLoaded"))
        page.on("load", lambda: lifecycle.append(f"{ms()}ms  load"))

        condition_met = False
        error: Optional[str] = None
        screenshot_png = b""
        mhtml = b""

        try:
            wait_until = "networkidle" if condition_type == "networkidle" else "load"
            await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            lifecycle.append(f"{ms()}ms  goto resolved")

            if condition_type in ("load", "networkidle"):
                condition_met = True
            elif condition_type == "css" and condition:
                try:
                    await page.wait_for_selector(condition, timeout=10_000)
                    condition_met = True
                    lifecycle.append(f"{ms()}ms  CSS found: {condition}")
                except Exception:
                    lifecycle.append(f"  CSS NOT found: {condition}")
            elif condition_type == "text" and condition:
                content = await page.content()
                condition_met = condition in content
                lifecycle.append(
                    f"  Text {'found' if condition_met else 'NOT found'}: {condition[:60]}"
                )

            await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)

            screenshot_png = await page.screenshot(
                full_page=True, type="png", animations="disabled"
            )
            lifecycle.append(f"{ms()}ms  screenshot ({len(screenshot_png) // 1024} KB)")

            cdp = await ctx.new_cdp_session(page)
            result = await cdp.send("Page.captureSnapshot", {"format": "mhtml"})
            mhtml = result["data"].encode("utf-8")
            lifecycle.append(f"{ms()}ms  MHTML ({len(mhtml) // 1024} KB)")
            await cdp.detach()

        except Exception as exc:
            error = str(exc)
            lifecycle.append(f"  ERROR: {error[:200]}")
        finally:
            await ctx.close()

        return CaptureResult(
            url=url, final_url=final_url, http_status=http_status,
            headers=resp_headers, mhtml=mhtml,
            mhtml_sha256=hashlib.sha256(mhtml).hexdigest() if mhtml else "",
            screenshot_png=screenshot_png, lifecycle_events=lifecycle,
            condition_met=condition_met, error=error,
        )


capture_service = CaptureService()
