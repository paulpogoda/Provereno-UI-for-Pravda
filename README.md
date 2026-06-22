<div align="center">

<!-- Logo SVG inline — renders on GitHub -->
<svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="31" cy="31" r="22" stroke="#01696f" stroke-width="4"/>
  <path d="M48 48L62 62" stroke="#01696f" stroke-width="4" stroke-linecap="round"/>
  <path d="M22 31l6.5 6.5L42 24" stroke="#01696f" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>

# Provereno UI for Pravda

**Self-hostable web archive interface for fact-checkers and newsrooms**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-teal.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com/)
[![PostgreSQL 15](https://img.shields.io/badge/PostgreSQL-15-336791)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://docs.docker.com/compose/)

[Overview](#overview) · [Features](#features) · [Quick Start](#quick-start) · [Configuration](#configuration) · [Architecture](#architecture) · [API](#api-reference) · [Contributing](#contributing)

</div>

---

## Overview

`provereno-ui-for-pravda` is an open-source, self-hostable web application that wraps [opensanctions/pravda](https://github.com/opensanctions/pravda) — a headless web archiving engine built on Playwright — with a team-facing UI and a public evidence viewer.

Built for investigative journalists and fact-checking teams who need to:

- **Archive** web pages with cryptographic integrity guarantees
- **Collaborate** on evidence across editorial teams with role-based access
- **Publish** tamper-evident public links to archived pages
- **Export** forensic receipts (ZIP packages with SHA-256 checksums) for editors and legal teams

Deploys in a single `docker compose up` on any Linux VPS with 2 GB RAM. No Google Cloud Console, no Kubernetes, no vendor lock-in.

---

## Features

| Feature | Description |
|---|---|
| 🔐 **GitHub OAuth** | Sign in via GitHub App — no passwords, no email verification |
| 👥 **Role-based access** | `admin` and `editor` roles; access list controlled via env variable |
| 📸 **Async capture** | Job queue via PostgreSQL `LISTEN/NOTIFY`; real-time SSE progress |
| 🗂 **Collections** | Group snapshots by investigation topic; add/remove with live filter |
| 🏷 **Tagging** | Arbitrary tags on snapshots; filter and bulk-tag from the archive |
| 📦 **Bulk CSV import** | Upload up to 500 URLs at once; drag-and-drop with per-job progress |
| 🔎 **Forensic receipt** | Downloadable ZIP: HTML + PNG + MHTML + JSON metadata + `sha256sums` |
| 🌐 **Public viewer** | Shareable evidence URL with OpenGraph meta, SHA-256 display, verify command |
| 📡 **URL monitoring** | Background `HEAD` checks; status `online / changed / deleted / blocked` |
| 📋 **Audit log** | Append-only log of 11 event types; CSV export; admin-only access |
| 🌙 **Dark mode** | System preference + manual toggle; full WCAG AA contrast |
| 🐳 **One-command deploy** | Docker Compose with PostgreSQL + Nginx + Playwright included |

---

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose v2
- A GitHub OAuth App ([create one here](https://github.com/settings/developers))
  - **Homepage URL:** `https://your-domain.org`
  - **Callback URL:** `https://your-domain.org/auth/callback`

### 1. Clone and configure

```bash
git clone https://github.com/Provereno-Media/Provereno-UI-for-Pravda.git
cd Provereno-UI-for-Pravda
cp .env.example .env
```

Edit `.env` — the four required fields:

```dotenv
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
SECRET_KEY=change_me_to_a_random_64_char_string
ALLOWED_GITHUB_LOGINS=alice,bob,carol   # comma-separated GitHub usernames
```

### 2. Start

```bash
docker compose up -d
```

The app is available at `http://localhost` (or your configured domain). First user to log in with an allowed GitHub handle receives the `editor` role. Promote to `admin` via:

```bash
docker compose exec app python -m provereno.cli promote-admin <github_login>
```

### 3. Verify the backend is up

```bash
curl http://localhost/health
# {"status":"ok"}
```

---

## Configuration

All configuration is via environment variables. No code changes are needed for a new deployment.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_CLIENT_ID` | ✅ | — | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | ✅ | — | GitHub OAuth App client secret |
| `SECRET_KEY` | ✅ | — | 64-char random string for session signing |
| `ALLOWED_GITHUB_LOGINS` | ✅ | — | Comma-separated GitHub usernames with access |
| `DATABASE_URL` | — | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `PRAVDA_API_URL` | — | `http://pravda:8000` | URL of the Pravda engine |
| `STORAGE_BACKEND` | — | `local` | `local`, `s3`, or `gcs` |
| `STORAGE_PATH` | — | `/data/snapshots` | Root path for local storage |
| `S3_BUCKET` | — | — | Bucket name for S3/GCS backend |
| `S3_ENDPOINT_URL` | — | — | Custom endpoint (for MinIO, Cloudflare R2, etc.) |
| `APP_TITLE` | — | `Provereno.Media` | Displayed name in UI and emails |
| `BASE_URL` | — | `http://localhost` | Canonical base URL for public links |
| `LOG_LEVEL` | — | `info` | `debug`, `info`, `warning`, `error` |

For S3-compatible storage (MinIO, Cloudflare R2, Backblaze B2), set `STORAGE_BACKEND=s3` and provide `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Nginx                            │
│          (TLS termination, static files, proxy)         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI app                           │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ pages router │  │ auth router  │  │  API routers │  │
│  │ (Jinja2 SSR) │  │(GitHub OAuth)│  │ snapshots /  │  │
│  └──────────────┘  └──────────────┘  │ collections /│  │
│                                      │ bulk / export│  │
│  ┌──────────────┐  ┌──────────────┐  └──────────────┘  │
│  │  job runner  │  │ url_monitor  │                     │
│  │(PG LISTEN/   │  │ (background  │                     │
│  │ NOTIFY queue)│  │  HEAD tasks) │                     │
│  └──────┬───────┘  └──────────────┘                     │
└─────────┼───────────────────────────────────────────────┘
          │
┌─────────▼──────────┐     ┌──────────────────────────────┐
│  PostgreSQL 15     │     │   opensanctions/pravda        │
│                    │     │   (Playwright, headless)      │
│  snapshots         │     │                               │
│  jobs              │◄────┤  POST /snapshots              │
│  collections       │     │  GET  /snapshots?url=...      │
│  tags              │     │  GET  /health                 │
│  audit_log         │     └──────────────────────────────┘
│  users             │
└────────────────────┘
```

### Key modules

| Module | Responsibility |
|---|---|
| `capture.py` | Submits capture jobs to Pravda, polls for completion |
| `jobs.py` | PostgreSQL-backed async job queue with SSE broadcast |
| `forensic.py` | Generates forensic receipt ZIP (HTML + PNG + MHTML + JSON + sha256sums) |
| `url_monitor.py` | Background scheduler for `HEAD` availability checks |
| `audit.py` | Append-only audit log writer (never deletes) |
| `auth.py` | Session management, role checks |
| `models.py` | SQLAlchemy ORM models |

---

## API Reference

The UI wraps the Pravda engine API. Core endpoints:

### `GET /health`
Returns `{"status": "ok"}` when the service is running.

### `GET /snapshots`

List snapshots for a URL.

```
GET /snapshots?url=https://example.com/article&page=1
```

```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "url": "https://example.com/article",
      "captured_at": "2026-06-22T09:56:31Z",
      "http_status": 200,
      "condition_type": "lifecycle",
      "condition": "networkidle",
      "condition_met": true,
      "lifecycle_events": ["DOMContentLoaded", "load", "networkidle"],
      "contents": [
        {"content_type": "screenshot", "path": "/data/snapshots/abc/screenshot.png"},
        {"content_type": "mhtml",      "path": "/data/snapshots/abc/page.mhtml"}
      ],
      "headers": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}]
    }
  ],
  "total": 1
}
```

### `POST /snapshots`

Trigger a new capture.

```json
{
  "url": "https://example.com/article",
  "condition_type": "lifecycle",
  "condition": "networkidle"
}
```

**Condition values:** `DOMContentLoaded` · `load` · `networkidle`

Full OpenAPI spec available at `/openapi.json` when the app is running.

---

## Forensic Receipt

Every snapshot can be exported as a verifiable ZIP package:

```
evidence-{id}.zip
├── receipt.html          # Human-readable forensic report with QR code
├── receipt.pdf           # Print-ready PDF version
├── screenshot.png        # Full-page screenshot
├── page.mhtml            # Complete page archive (download only, never served inline)
├── metadata.json         # URL, timestamps, HTTP headers, capture conditions
└── sha256sums.txt        # Checksums for all files above
```

Verify integrity on any machine:

```bash
cd evidence-{id}/
sha256sum -c sha256sums.txt
```

---

## Public Evidence Links

Archived pages can be published as public links — no login required:

```
https://your-domain.org/evidence/{snapshot-id}
```

Each public page displays the archived URL, capture timestamp, HTTP status, SHA-256 hash of the MHTML, and the availability status of the original URL. OpenGraph metadata enables rich previews when shared on social media.

MHTML files are **never served inline** to prevent script execution. Only the screenshot and metadata are displayed in the browser.

---

## Audit Log

All significant actions are recorded in an append-only audit log accessible to `admin` users at `/audit`. The log captures:

`snapshot.created` · `snapshot.deleted` · `snapshot.exported` · `snapshot.published` · `snapshot.unpublished` · `user.login` · `user.logout` · `bulk.started` · `tag.added` · `tag.removed` · `collection.created`

Audit records are never deleted through the UI and can be exported as CSV.

---

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run PostgreSQL locally
docker compose up -d postgres pravda

# Start the app with auto-reload
uvicorn provereno.main:app --reload --port 8080

# Run tests
pytest
```

### Project structure

```
provereno/
├── main.py               # App factory, router registration
├── models.py             # SQLAlchemy ORM models
├── config.py             # Pydantic settings
├── capture.py            # Pravda integration
├── jobs.py               # Async job queue
├── forensic.py           # Forensic receipt generator
├── url_monitor.py        # Background availability checker
├── audit.py              # Audit log writer
├── auth.py               # Session helpers
├── routers/
│   ├── auth.py           # GitHub OAuth flow
│   ├── pages.py          # Server-rendered UI routes
│   ├── snapshots.py      # Snapshot CRUD
│   ├── collections.py    # Collections CRUD
│   ├── bulk.py           # CSV bulk import
│   ├── export.py         # Forensic receipt download
│   ├── public.py         # Public evidence viewer
│   └── job_routes.py     # SSE job progress
├── templates/            # Jinja2 templates (12 files)
└── static/
    └── style.css         # Design system (CSS custom properties)
```

---

## Contributing

Contributions are welcome. Please open an issue before starting significant work.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Follow the existing code style (PEP 8, type hints on all public functions)
4. Add or update tests for your changes
5. Open a pull request against `main`

### Code of Conduct

This project is intended for journalists, researchers, and fact-checkers working in the public interest. Contributions that would facilitate surveillance, harassment, or censorship will not be accepted.

---

## License

[GNU Affero General Public License v3.0](LICENSE)

Any newsroom or organisation running a modified version of this software must publish their changes under the same license.

---

<div align="center">

Built by [Provereno.Media](https://provereno.media) · Evidence layer powered by [opensanctions/pravda](https://github.com/opensanctions/pravda)

</div>
