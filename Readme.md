# TravelBuddy

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python Version](https://img.shields.io/badge/python-3.11+-blue)

TravelBuddy is a FastAPI application for tracking travel expenses, enforcing trip budgets, and experimenting with exchange-rate strategies. The service ships with a web UI and REST endpoints, plus smoke-test scripts for validating rate and budget scenarios.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Clone and Install](#clone-and-install)
  - [Run the API](#run-the-api)
  - [Run with Docker](#run-with-docker)
- [Configuration](#configuration)
- [Data & Persistence](#data--persistence)
- [Checks & Tooling](#checks--tooling)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Features

- Expense capture with category, currency, and timeline views delivered via FastAPI routers.
- Configurable budgeting rules including caps, auto-creation, and default per-currency allowances.
- Exchange-rate providers with caching and optional HTTP-based lookups for experimentation.
- Tailwind-powered UI templates served alongside the API for settings and analytics dashboards.
- Structured logging, request correlation, and graceful error handling baked into the app factory.

## Tech Stack

- **Runtime:** Python 3.11, FastAPI, Starlette
- **Templates:** Jinja2 with static assets in `app/static`
- **HTTP client:** httpx for external exchange-rate probes
- **Packaging:** Dockerfile + `compose.yml` for local container orchestration

## Quick Start

### Prerequisites

- Python 3.11 or newer
- `pip` and `virtualenv` (or `python -m venv`)
- Git

### Clone and Install

```bash
git clone https://github.com/your-org/travelbuddy.git
cd travelbuddy
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

The application performs lightweight SQLite migrations at startup and listens on `http://127.0.0.1:8000`. Visit `/ui/settings` to adjust budgeting and rate behavior or `/docs` for the generated OpenAPI spec.

### Run with Docker

```bash
docker compose up --build
```

- Maps the service to `http://127.0.0.1:8005`
- Persists data in the named `app_data` volume
- Follows configuration hints in `compose.yml` (override settings with `docker compose --env-file` as needed)

Stop with `docker compose down` (add `-v` to drop the volume).

## Configuration

Pydantic settings load from environment variables and the optional `.env` file (see `SETTINGS.md` for full detail). Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_NAME` | `Travel Expense Tracker` | Application title exposed in metadata |
| `DEBUG` | `true` | Enables verbose logging and FastAPI debug mode |
| `DATA_DIR` | `data` | Directory used for SQLite and cached assets |
| `DB_FILENAME` | `app.sqlite3` | SQLite filename inside `DATA_DIR` |
| `RATES_CACHE_TTL_SECONDS` | `3600` | Cache lifetime for exchange rates |
| `EXCHANGE_RATE_PROVIDER` | `static` | Provider selector: `static`, `external-placeholder`, `external-http` |
| `EXCHANGE_API_BASE_URL` | `https://api.exchangerate-api.com/v4/latest` | Base URL used by HTTP provider |
| `HTTP_TIMEOUT_SECONDS` | `5.0` | Timeout for outbound rate requests |
| `ENABLE_RATE_OVERRIDE` | `true` | Allows manual rate overrides in the UI |

When the server boots it ensures `DATA_DIR` exists and computes an absolute SQLite path. Settings tweaked in the UI are stored in the `metadata` table and take priority over environment defaults.

## Data & Persistence

- SQLite database lives in `data/app.sqlite3` by default (created automatically).
- Database schema migrations run on startup via `app.db.migrate.apply_migrations`.
- Sample seed helpers and DAL logic reside in `app/db`; see `seed.py` for populating fixtures when needed.

## Checks & Tooling

Smoke-test scripts under `scripts/` cover budget and FX behaviors. Execute them with:

```bash
python -m scripts.smoke_rate_cache
python -m scripts.smoke_forex
```

Add new scripts alongside existing ones to exercise additional scenarios. At the moment no formal pytest suite ships with the repo.

## Project Structure

```
.
app/
  core/          # Settings, logging, error handlers
  db/            # SQLite schema, migrations, data access
  models/        # Pydantic models used across routers
  routers/       # FastAPI routers (budgets, expenses, analytics, UI, etc.)
  services/      # Domain services and settings helpers
  static/        # Compiled CSS/JS assets
  templates/     # Jinja2 templates for the web UI
assets/          # Source assets (e.g., Tailwind input CSS)
data/            # Runtime data directory (ignored by Git)
docs/            # Product requirements and task breakdowns
scripts/         # Smoke-test and utility scripts
Dockerfile
compose.yml
requirements.txt
SETTINGS.md
```

## Documentation

- `SETTINGS.md` - exhaustive catalogue of runtime settings and how the UI persists them.
- `docs/prd.md` - product requirements document.
- `docs/task_sheet.md` - engineering notes and work-breakdown structure.

## Contributing

Pull requests and issue reports are welcome. Please open an issue to discuss substantial changes before submitting a PR so we can align on scope and guardrails.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
