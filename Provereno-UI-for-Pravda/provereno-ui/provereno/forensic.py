from __future__ import annotations
import hashlib, io, json, zipfile
from datetime import datetime
from typing import Optional

try:
    from weasyprint import HTML as WeasyHTML
    _WEASYPRINT = True
except Exception:
    _WEASYPRINT = False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipt_html(meta: dict, mhtml_sha256: str, screenshot_sha256: str) -> bytes:
    url           = meta.get("url", "")
    captured_at   = meta.get("captured_at", "")
    final_url     = meta.get("final_url", url)
    http_status   = meta.get("http_status", "")
    snapshot_id   = meta.get("snapshot_id", "")
    condition_type= meta.get("condition_type", "")
    condition     = meta.get("condition", "")
    condition_met = meta.get("condition_met", False)
    creator       = meta.get("creator", "")
    lifecycle     = meta.get("lifecycle_events", [])
    headers       = meta.get("headers", {})

    cond_color = "#437a22" if condition_met else "#a12c7b"
    cond_bg    = "#d4dfcc" if condition_met else "#e0ced7"
    cond_label = "Condition met" if condition_met else "Condition NOT met"

    lc_rows = "".join(
        "<tr><td style='font-family:monospace;font-size:11px;color:#666;padding:2px 0'>"
        + e + "</td></tr>" for e in lifecycle
    )
    hdr_rows = "".join(
        "<tr><td style='color:#555;font-size:11px;padding:2px 8px'>" + k +
        "</td><td style='font-size:11px;padding:2px 8px;word-break:break-all'>" + v +
        "</td></tr>" for k, v in list(headers.items())[:30]
    )
    lc_section = ("<div class='sec'><h2>Lifecycle Events</h2><table>"
                  + lc_rows + "</table></div>") if lifecycle else ""
    hdr_section = ("<div class='sec'><h2>HTTP Response Headers</h2><table>"
                   + hdr_rows + "</table></div>") if headers else ""

    html = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        "<title>Forensic Evidence Receipt</title>"
        "<style>"
        "body{font-family:Helvetica,Arial,sans-serif;margin:0;padding:32px;"
        "color:#28251d;background:#f7f6f2;font-size:13px;line-height:1.6}"
        ".hdr{display:flex;align-items:center;gap:14px;margin-bottom:28px;"
        "border-bottom:2px solid #01696f;padding-bottom:18px}"
        "h1{margin:0;font-size:20px;font-weight:700;color:#01696f}"
        ".sub{font-size:12px;color:#7a7974;margin:2px 0 0}"
        ".sec{background:#fff;border:1px solid #d4d1ca;border-radius:8px;"
        "padding:16px 20px;margin-bottom:16px}"
        "h2{margin:0 0 12px;font-size:13px;font-weight:600;"
        "border-bottom:1px solid #dcd9d5;padding-bottom:6px}"
        "table{width:100%;border-collapse:collapse}"
        "td{padding:4px 0;vertical-align:top}"
        "td:first-child{width:180px;color:#7a7974;font-size:12px}"
        ".hash{font-family:'Courier New',monospace;font-size:10px;color:#555;"
        "background:#f3f0ec;padding:2px 5px;border-radius:3px;word-break:break-all}"
        ".badge{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;"
        "background:" + cond_bg + ";color:" + cond_color + "}"
        ".footer{text-align:center;margin-top:28px;font-size:10px;color:#bab9b4}"
        "</style></head><body>"
        "<div class='hdr'>"
        "<svg width='44' height='44' viewBox='0 0 28 28' fill='none'>"
        "<circle cx='12' cy='12' r='8' stroke='#01696f' stroke-width='2.2'/>"
        "<path d='M17.5 17.5L24 24' stroke='#01696f' stroke-width='2.2' stroke-linecap='round'/>"
        "<path d='M9 12l2 2 4-4' stroke='#01696f' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>"
        "</svg>"
        "<div><h1>Forensic Evidence Receipt</h1>"
        "<p class='sub'>Provereno.Media — tamper-evident web archive</p></div></div>"
        "<div class='sec'><h2>Capture Details</h2><table>"
        "<tr><td>Snapshot ID</td><td><span class='hash'>" + snapshot_id + "</span></td></tr>"
        "<tr><td>Captured at</td><td>" + captured_at + " UTC</td></tr>"
        "<tr><td>Captured by</td><td>" + (creator or "—") + "</td></tr>"
        "<tr><td>Target URL</td><td style='word-break:break-all;color:#01696f'>" + url + "</td></tr>"
        "<tr><td>Final URL</td><td style='word-break:break-all;color:#01696f'>" + final_url + "</td></tr>"
        "<tr><td>HTTP status</td><td>" + str(http_status) + "</td></tr>"
        "<tr><td>Condition</td><td>" + condition_type + ": <code>" + (condition or "—") + "</code></td></tr>"
        "<tr><td>Condition result</td><td><span class='badge'>" + cond_label + "</span></td></tr>"
        "</table></div>"
        "<div class='sec'><h2>File Integrity (SHA-256)</h2><table>"
        "<tr><td>page.mhtml</td><td><span class='hash'>" + mhtml_sha256 + "</span></td></tr>"
        "<tr><td>screenshot.png</td><td><span class='hash'>" + screenshot_sha256 + "</span></td></tr>"
        "</table></div>"
        + lc_section + hdr_section +
        "<p class='footer'>Provereno.Media &bull; " + captured_at + " UTC &bull; "
        "sha256(mhtml)=" + mhtml_sha256[:16] + "...</p>"
        "</body></html>"
    )
    return html.encode("utf-8")


def build_forensic_zip(
    *,
    snapshot_id: str,
    url: str,
    final_url: str,
    http_status: int,
    headers: dict,
    mhtml: bytes,
    mhtml_sha256: str,
    screenshot_png: bytes,
    lifecycle_events: list,
    condition_type: str,
    condition: Optional[str],
    condition_met: bool,
    captured_at,
    creator: Optional[str],
    tags: list,
    note: Optional[str],
) -> bytes:
    captured_str = (
        captured_at.strftime("%Y-%m-%dT%H:%M:%S")
        if hasattr(captured_at, "strftime")
        else str(captured_at)
    )
    meta = {
        "snapshot_id": snapshot_id, "url": url, "final_url": final_url,
        "http_status": http_status, "headers": headers,
        "mhtml_sha256": mhtml_sha256, "condition_type": condition_type,
        "condition": condition, "condition_met": condition_met,
        "captured_at": captured_str, "creator": creator,
        "tags": tags, "note": note, "lifecycle_events": lifecycle_events,
    }

    screenshot_sha256 = _sha256(screenshot_png)
    metadata_json     = json.dumps(meta, ensure_ascii=False, indent=2).encode()
    receipt_html      = _receipt_html(meta, mhtml_sha256, screenshot_sha256)

    shasums = (
        mhtml_sha256       + "  page.mhtml\n"
        + screenshot_sha256 + "  screenshot.png\n"
        + _sha256(metadata_json) + "  metadata.json\n"
        + _sha256(receipt_html)  + "  receipt.html\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("page.mhtml",     mhtml)
        zf.writestr("screenshot.png", screenshot_png)
        zf.writestr("metadata.json",  metadata_json)
        zf.writestr("receipt.html",   receipt_html)
        if _WEASYPRINT:
            try:
                pdf = WeasyHTML(string=receipt_html.decode()).write_pdf()
                shasums += _sha256(pdf) + "  receipt.pdf\n"
                zf.writestr("receipt.pdf", pdf)
            except Exception:
                pass
        zf.writestr("sha256sums.txt", shasums.encode())
    return buf.getvalue()
