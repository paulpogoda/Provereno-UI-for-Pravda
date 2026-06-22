# Provereno UI v1.1

FastAPI + Jinja2 + Alpine.js forensic web archive frontend.

## Quick Start

    cp .env.example .env
    # Fill GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, SESSION_SECRET_KEY
    docker compose up -d
    # Visit http://localhost:8080

## Manual dev

    python -m venv .venv && source .venv/bin/activate
    pip install -e .
    playwright install chromium
    uvicorn provereno.main:app --reload --port 8080

## Features

- GitHub OAuth auth
- Playwright Chromium capture (MHTML + PNG via CDP)
- SSE real-time progress (single + bulk)
- Forensic ZIP: receipt.html + receipt.pdf (WeasyPrint) + MHTML + screenshot + sha256sums
- Public evidence viewer (/public/evidence/{id})
- Collections (group snapshots by investigation)
- Tags with autocomplete
- Bulk CSV import (500 URLs)
- URL availability monitor
- Audit log (admin only)
- Dark/light mode
