<div align="center">

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
<img src="https://github.com/user-attachments/assets/6db1309b-53c4-4f6c-8a8f-3886bd838310" />

[HTML-Mockup is here](https://provereno-media.github.io/Provereno-UI-for-Pravda/)

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
| 🔐 **GitHub OAuth** | Sign in via GitHub — restrict access by organisation and/or individual usernames |
| 👥 **Role-based access** | `admin` and `editor` roles; controlled entirely via env variables |
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
cd Provereno-UI-for-Pravda/provereno-ui
cp .env.example .env
```

Open `.env` and fill in the required fields:

```dotenv
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
SESSION_SECRET_KEY=change_me_to_a_random_32char_string

# Grant access by GitHub organisation, individual logins, or both.
# At least one of the two must be set.
ALLOWED_GITHUB_ORGS=your-org
ALLOWED_GITHUB_LOGINS=alice,bob
```

Generate a strong `SESSION_SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Start

```bash
docker compose up -d
```

The app is available at `http://localhost`. The first user to sign in with a permitted GitHub account receives the `editor` role. Promote to `admin`:

```bash
docker compose exec app python -m provereno.cli promote-admin <github_login>
```

### 3. Verify

```bash
curl http://localhost/health
# {"status":"ok"}
```

---

## Configuration

All configuration is via environment variables. No code changes are needed to deploy for a new organisation.

### Required

| Variable | Description |
|---|---|
| `GITHUB_CLIENT_ID` | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |
| `SESSION_SECRET_KEY` | Random 32-char string for session signing |
| `ALLOWED_GITHUB_ORGS` **or** `ALLOWED_GITHUB_LOGINS` | At least one must be set (see below) |

### Access control

Access is granted when a user satisfies **either** condition:

```dotenv
# Allow all members of a GitHub organisation
ALLOWED_GITHUB_ORGS=my-newsroom

# Allow specific individuals regardless of org membership
ALLOWED_GITHUB_LOGINS=alice,bob,carol

# Both can be set simultaneously
```

### Optional

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://provereno:provereno@localhost:5434/provereno` | PostgreSQL connection string |
| `PRAVDA_API_URL` | `http://pravda:8000` | URL of the Pravda engine |
| `DATA_DIR` | `./data` | Root directory for captured snapshots |
| `APP_TITLE` | `Provereno.Media` | Displayed name in the UI |
| `BASE_URL` | `http://localhost` | Canonical base URL for public evidence links |
| `LOG_LEVEL` | `info` | `debug` · `info` · `warning` · `error` |

> **Note:** PostgreSQL is exposed on port **5434** by default (not the standard 5432) to avoid conflicts with existing local instances.

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
│  (port 5434)       │     │   (Playwright, headless)      │
│                    │     │                               │
│  snapshots         │◄────┤  POST /snapshots              │
│  jobs              │     │  GET  /snapshots?url=...      │
│  collections       │     │  GET  /health                 │
│  tags              │     └──────────────────────────────┘
│  audit_log         │
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

The UI wraps the Pravda engine API. Core endpoints (base URL `http://localhost:8000`):

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### `GET /snapshots`

List snapshots for a URL.

```bash
curl "http://localhost:8000/snapshots?url=https://example.com/article&page=1"
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
        {"content_type": "screenshot", "path": "./data/snapshots/abc/screenshot.png"},
        {"content_type": "mhtml",      "path": "./data/snapshots/abc/page.mhtml"}
      ],
      "headers": [
        {"name": "Content-Type", "value": "text/html; charset=utf-8"}
      ]
    }
  ],
  "total": 1
}
```

### `POST /snapshots`

Trigger a new capture.

```bash
curl -X POST http://localhost:8000/snapshots \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "condition_type": "lifecycle", "condition": "networkidle"}'
```

**Condition values:** `DOMContentLoaded` · `load` · `networkidle`

Full OpenAPI spec: `http://localhost:8000/openapi.json`

---

## Forensic Receipt

Every snapshot can be exported as a verifiable ZIP package via the UI or `GET /export/{id}`:

```
evidence-{id}.zip
├── receipt.html       # Human-readable forensic report with QR code
├── receipt.pdf        # Print-ready PDF version
├── screenshot.png     # Full-page screenshot
├── page.mhtml         # Complete page archive (download only, never served inline)
├── metadata.json      # URL, timestamps, HTTP headers, capture conditions
└── sha256sums.txt     # Checksums for all files above
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

Each public page shows the archived URL, capture timestamp, HTTP status, SHA-256 hash of the MHTML, and the live availability status of the original URL. OpenGraph metadata enables rich previews when shared on social media.

> MHTML files are **never served inline** to prevent script execution. Only the screenshot and metadata are rendered in the browser.

---

## Audit Log

All significant actions are recorded in an append-only log, accessible to `admin` users at `/audit`. Logged event types:

`snapshot.created` · `snapshot.deleted` · `snapshot.exported` · `snapshot.published` · `snapshot.unpublished` · `user.login` · `user.logout` · `bulk.started` · `tag.added` · `tag.removed` · `collection.created`

Records are never deleted through the UI and can be exported as CSV.

---

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL and Pravda (port 5434)
docker compose up -d postgres pravda

# Start the app with auto-reload
cd provereno-ui
uvicorn provereno.main:app --reload --port 8080

# Run tests
pytest
```

### Project structure

```
provereno-ui/
├── .env.example
├── docker-compose.yml
├── nginx.conf
├── pyproject.toml
└── provereno/
    ├── main.py            # App factory, router registration
    ├── models.py          # SQLAlchemy ORM models
    ├── config.py          # Pydantic settings
    ├── capture.py         # Pravda integration
    ├── jobs.py            # Async job queue
    ├── forensic.py        # Forensic receipt generator
    ├── url_monitor.py     # Background availability checker
    ├── audit.py           # Audit log writer
    ├── auth.py            # Session helpers
    ├── routers/
    │   ├── auth.py        # GitHub OAuth flow
    │   ├── pages.py       # Server-rendered UI routes
    │   ├── snapshots.py   # Snapshot CRUD
    │   ├── collections.py # Collections CRUD
    │   ├── bulk.py        # CSV bulk import
    │   ├── export.py      # Forensic receipt download
    │   ├── public.py      # Public evidence viewer
    │   └── job_routes.py  # SSE job progress
    ├── templates/         # Jinja2 templates (12 files)
    └── static/
        └── style.css      # Design system (CSS custom properties)
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

## Support the project

The project is maintained by a small independent newsroom. If you find it useful, consider supporting us on [Patreon](https://patreon.com/provereno).

---

## License

[GNU Affero General Public License v3.0](LICENSE)

Any newsroom or organisation running a modified version of this software must publish their changes under the same license.

---

<div align="center">

Built by [Provereno.Media](https://provereno.media) · Evidence layer powered by [opensanctions/pravda](https://github.com/opensanctions/pravda)

</div>
