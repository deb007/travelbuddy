# Travel Expense Tracker – MVP Task Sheet

Tech Stack: FastAPI (backend + API), Jinja2 (server-side templating), SQLite (persistent local DB), Vanilla JS (progressive enhancement), Tailwind CSS.

Status Legend: Not Started | In Progress | Blocked | Review | Done
Priority Legend: P0 (Critical for MVP) | P1 (Important) | P2 (Nice-to-have / Stretch)
Phase Mapping: Phase 1 (Core + Budget + Logging), Phase 2 (Analytics + Exchange Rate), Phase 3 (UI Polish + Testing + Deployment)

> All tasks default to Status: Not Started, What Was Done: (empty until progress), and are ordered roughly by dependency flow.

---
## 1. High-Level Epics
- E1 Project Setup & Infrastructure
- E2 Data Layer & Models
- E3 Budget & Forex Configuration
- E4 Expense Logging Core
- E5 Timeline (Pre-Trip vs Trip) Handling
- E6 Forex Card Tracking
- E7 Exchange Rate Integration
- E8 Spending Analytics & Metrics
- E9 UI / Templates / UX
- E10 Alerts & Threshold Logic
- E11 Offline Support (basic)
- E12 Testing & QA
- E13 Deployment & Ops
- E14 Documentation & Housekeeping

---
## 2. Task Table

### E1 Project Setup & Infrastructure
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T01.01 | Project Init | Repo structure | P0 | Create FastAPI project skeleton (`app/`), config module, main entry. |  | Done | Created `app/` with `__init__.py`, `core/config.py` (pydantic Settings), `routers/health.py`, and `main.py` with `create_app()` & root + /health endpoints. | App starts, `/health` returns 200. |
| T01.02 | Project Init | Dependency mgmt | P0 | Add `requirements.txt` (FastAPI, Uvicorn, Jinja2, pydantic, httpx). | T01.01 | Done | Added `requirements.txt` with pinned versions: fastapi 0.111.0, uvicorn[standard] 0.30.0, jinja2 3.1.4, httpx 0.27.0, pydantic 1.10.15, python-multipart 0.0.9; import smoke test passed. | All deps install; server runs. |
| T01.03 | Config | Settings loader | P1 | Centralize env/settings (rates cache TTL, DB path). | T01.01 | Done | Extended `Settings` with data_dir, db_filename, derived db_path, rates_cache_ttl_seconds, exchange_api_base_url, http_timeout_seconds, enable_rate_override; ensures data dir creation; verified env overrides (DB_FILENAME, RATES_CACHE_TTL_SECONDS). | Override via env vars works. |
| T01.04 | Infra | Logging setup | P1 | Structured logging (info, warn, error). | T01.01 | Done | Implemented `core/logging.py` with JSON formatter, request id ContextVar + middleware, init_logging() invoked in app factory; verified stdout logs & request-scoped IDs via test client. | Logs appear with request id. |
| T01.05 | Infra | Error handlers | P1 | Global exception handlers for 404, validation, 500. | T01.01 | Done | Added `core/errors.py` with handlers (not_found, validation_error, server_error); registered in `create_app`; smoke tested 404 & generic path; logs capture exceptions. | Proper JSON error payloads. |

### E2 Data Layer & Models
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T02.01 | DB | SQLite schema design | P0 | Translate PRD models to SQL tables (expenses, budgets, forex_cards, exchange_rates, metadata). | T01.01 | Done | Implemented `db/schema.py` with idempotent DDL for: budgets, forex_cards, exchange_rates, expenses, metadata; added init_db() utility and verified table creation. | Tables created correctly. |
| T02.02 | DB | Migration script | P0 | Simple bootstrap migration (idempotent create tables). | T02.01 | Not Started |  | Running twice is safe. |
| T02.03 | Models | Pydantic models | P0 | ExpenseIn, ExpenseOut, Budget, ForexCard, RateRecord. | T02.01 | Not Started |  | Validation errors on bad input. |
| T02.04 | DAL | CRUD utilities | P0 | Abstract DB access (insert expense, list, update spent). | T02.02 | Not Started |  | Insert/select roundtrip integrity. |
| T02.05 | DAL | Aggregation queries | P1 | Helpers for sums by currency, category, date. | T02.04 | Not Started |  | Correct sums vs manual calc. |

### E3 Budget & Forex Configuration
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T03.01 | Budget | Budget table & seed | P0 | Store max & spent for INR/SGD/MYR. | T02.01 | Not Started |  | Defaults persisted. |
| T03.02 | Budget | Budget update endpoint | P0 | POST/PUT to set/modify max budgets. | T03.01 | Not Started |  | Update persists; constraints. |
| T03.03 | Budget | Spent auto-update | P0 | Increment spent when expense logged (same currency). | T04.02 | Not Started |  | Spent matches sum of expenses. |
| T03.04 | Budget | Remaining calc util | P0 | Helper returns remaining & thresholds (80%, 90%). | T03.03 | Not Started |  | Correct threshold flags. |

### E4 Expense Logging Core
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T04.01 | Expense | Validation rules | P0 | Validate currency, category, payment method, date range. | T02.03 | Not Started |  | Reject invalid combos. |
| T04.02 | Expense | Create endpoint | P0 | POST /expenses creates record & INR equivalent. | T07.03, T04.01 | Not Started |  | 201 response; stored data exact. |
| T04.03 | Expense | List endpoint | P0 | GET /expenses (filters: date range, currency, phase). | T04.02 | Not Started |  | Filter accuracy. |
| T04.04 | Expense | Edit endpoint | P1 | PATCH /expenses/{id} adjust amounts & budgets delta. | T04.02, T03.03 | Not Started |  | Budgets recalc on edit. |
| T04.05 | Expense | Delete endpoint | P1 | DELETE /expenses/{id} reverse budget spent. | T04.02, T03.03 | Not Started |  | Spent decreases correctly. |

### E5 Timeline Handling
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T05.01 | Timeline | Trip date config | P0 | Store start/end dates in metadata. | T02.01 | Not Started |  | Persist & retrieve dates. |
| T05.02 | Timeline | Phase resolver | P0 | Utility: given date -> pre-trip or trip. | T05.01 | Not Started |  | Edge boundary dates. |
| T05.03 | Timeline | Filter integration | P1 | Phase filter param uses resolver. | T05.02 | Not Started |  | Pre-trip returns earlier expenses. |

### E6 Forex Card Tracking
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T06.01 | Forex | Schema & model | P0 | Track loaded & spent for SGD/MYR forex cards. | T02.01 | Not Started |  | CRUD integrity. |
| T06.02 | Forex | Load/adjust endpoint | P1 | Modify loaded amount. | T06.01 | Not Started |  | Prevent negative values. |
| T06.03 | Forex | Deduct on expense | P0 | If paymentMethod=forex: increment spent & available. | T04.02, T06.01 | Not Started |  | Correct balance after sequence. |
| T06.04 | Forex | Low balance alert hook | P1 | Flag when remaining <20%. | T06.03 | Not Started |  | Alert triggers at threshold. |

### E7 Exchange Rate Integration
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T07.01 | Rates | Config provider choice | P0 | Choose API (ExchangeRate-API or fallback). | T01.03 | Not Started |  | Config switch works. |
| T07.02 | Rates | HTTP client util | P0 | Reusable httpx wrapper with timeout/retry. | T01.04 | Not Started |  | Retry on transient failure. |
| T07.03 | Rates | Fetch & cache service | P0 | Cache INR-SGD, INR-MYR for 1h. | T07.02 | Not Started |  | Cache invalidates post TTL. |
| T07.04 | Rates | Manual override endpoint | P1 | POST to set manual rates if API down. | T07.03 | Not Started |  | Manual wins until expiry. |
| T07.05 | Rates | INR equivalent calc | P0 | Utility used when logging expenses. | T07.03 | Not Started |  | Precision & rounding rules. |

### E8 Spending Analytics & Metrics
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T08.01 | Analytics | Daily totals query | P0 | Sum INR equivalent per day. | T02.05 | Not Started |  | Correct daily sums. |
| T08.02 | Analytics | Average daily spend | P0 | total_spent / days_elapsed. | T08.01, T05.02 | Not Started |  | Matches manual calc. |
| T08.03 | Analytics | Remaining daily budget | P0 | (remaining_budget / days_left). | T03.04, T05.02 | Not Started |  | Edge last day division. |
| T08.04 | Analytics | Currency breakdown | P1 | Aggregation per currency. | T02.05 | Not Started |  | Sums vs raw expenses. |
| T08.05 | Analytics | Category breakdown | P1 | Percent & absolute per category. | T02.05 | Not Started |  | Percent sums to ~100%. |
| T08.06 | Analytics | Trend data endpoint | P1 | Endpoint for chart (daily). | T08.01 | Not Started |  | Ordered chronologically. |

### E9 UI / Templates / UX (Jinja2)
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T09.01 | UI | Base layout template | P0 | Shared head, nav (phase indicator). | T01.01 | Not Started |  | Blocks extend properly. |
| T09.02 | UI | Dashboard template | P0 | Progress bars, top metrics, exchange rates. | T03.04, T08.02 | Not Started |  | Correct numbers shown. |
| T09.03 | UI | Expense entry form | P0 | Amount, currency picker, category tags, payment method, date picker. | T04.02 | Not Started |  | Validation messages. |
| T09.04 | UI | Expense list view | P0 | Group by date, edit/delete actions. | T04.03 | Not Started |  | Sorting & grouping. |
| T09.05 | UI | Analytics view | P1 | Charts placeholders (server-render numeric; charts optional). | T08.05 | Not Started |  | Data consistency vs API. |
| T09.06 | UI | Alerts UI indicators | P1 | Visual cues for 80%,90%, low forex balance. | T03.04, T06.04 | Not Started |  | Colors/labels match conditions. |
| T09.07 | UI | Mobile responsiveness | P1 | Flex/grid tweaks for small screens. | T09.02 | Not Started |  | No horizontal scroll. |
| T09.08 | UI | Accessibility pass | P2 | Labels, aria, contrast. | T09.07 | Not Started |  | Lighthouse a11y score. |

### E10 Alerts & Threshold Logic
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T10.01 | Alerts | Budget threshold logic | P0 | 80%, 90% flags from budget util. | T03.04 | Not Started |  | Trigger at correct boundaries. |
| T10.02 | Alerts | Forex low balance logic | P1 | <20% remaining flag. | T06.04 | Not Started |  | Edge at exactly 20%. |
| T10.03 | Alerts | Aggregation surface | P1 | Provide list of active alerts to UI. | T10.01 | Not Started |  | Multiple alerts display. |

### E11 Offline Support (Basic)
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T11.01 | Offline | Service worker skeleton | P2 | Cache static assets + fallback page. | T09.01 | Not Started |  | Installs; assets cached. |
| T11.02 | Offline | Queue expense fallback | P2 | (Stretch) Queue form posts offline & sync later. | T04.02, T11.01 | Not Started |  | Create offline then sync. |

### E12 Testing & QA
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T12.01 | Tests | Unit: models & utils | P0 | Test budget calc, phase resolver, rate cache. | T03.04, T05.02, T07.03 | Not Started |  | Edge cases & rounding. |
| T12.02 | Tests | Unit: DAL CRUD | P0 | Insert/select/update/delete reliability. | T02.04 | Not Started |  | Data persists correctly. |
| T12.03 | Tests | API integration | P0 | Expense lifecycle, budgets adjust, forex deduction. | T04.*, T03.*, T06.* | Not Started |  | HTTP status & payloads. |
| T12.04 | Tests | Analytics correctness | P1 | Daily avg, remaining daily budget accuracy. | T08.* | Not Started |  | Derived values vs manual calc. |
| T12.05 | Tests | UI smoke (templating) | P1 | Render templates without errors. | T09.* | Not Started |  | Key pages 200 & content. |
| T12.06 | Tests | Alert scenarios | P1 | Budget thresholds & low forex triggers. | T10.* | Not Started |  | Alerts appear/disappear timely. |

### E13 Deployment & Ops
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T13.01 | Deploy | Run config | P0 | Uvicorn command parameters (host/port). | T01.01 | Not Started |  | App boots via script. |
| T13.02 | Deploy | Simple process script | P1 | `run.sh` / Windows equivalent for local start. | T13.01 | Not Started |  | Script runs w/out errors. |
| T13.03 | Deploy | SQLite backup note | P2 | Doc manual copy for backup. | T14.02 | Not Started |  | Instructions clear. |

### E14 Documentation & Housekeeping
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T14.01 | Docs | README MVP usage | P0 | Setup, run, basic workflow. | T01.*, T04.* | Not Started |  | Steps reproducible. |
| T14.02 | Docs | Data model reference | P1 | Tables & fields documented. | T02.01 | Not Started |  | Matches actual schema. |
| T14.03 | Docs | API endpoint list | P1 | Route, method, brief payload description. | T04.*, T07.*, T08.* | Not Started |  | Accuracy of endpoints. |
| T14.04 | Docs | Testing guide | P2 | How to run tests & interpret results. | T12.* | Not Started |  | Commands function. |
| T14.05 | Docs | Changelog init | P2 | Track MVP iterations. |  | Not Started |  | Entries follow format. |

---
## 3. Dependency Graph (Summary)
- Core order: Setup -> DB -> Budget/Forex -> Expenses -> Rates -> Analytics -> UI -> Alerts -> Testing -> Deployment -> Docs.
- Expense creation depends on rate fetch (for INR equivalent) and budget updates.
- Analytics depends on expenses + budgets + timeline.

## 4. Risk & Mitigation Notes
| Risk | Impact | Mitigation |
|------|--------|-----------|
| Exchange rate API downtime | INR equivalent blocked | Manual override endpoint (T07.04) |
| Incorrect budget sync on edit/delete | Misleading remaining budget | Strong unit + integration tests (T12.02/T12.03) |
| Rounding differences in analytics | User confusion | Centralized rounding util + tests |
| Forex card negative balance | Data inconsistency | Validation before deduct; transaction-like DAL pattern |
| Large future enhancements creeping in | Scope creep | Strict MVP P0 focus; defer P2 tasks if time constrained |

## 5. Acceptance Criteria (MVP Definition of Done)
- Able to configure budgets, trip dates, and forex card loads.
- Log, edit, delete expenses with immediate budget & forex balance reflection.
- View dashboard with current spend, remaining, daily average, daily remaining allowance.
- View analytics (at least numeric summaries; charts optional if time allows).
- Exchange rates auto-refresh hourly with manual override fallback.
- Threshold alerts visible for budgets (80%, 90%) and low forex (<20%).
- All P0 tasks Done; majority of P1 tasks for usable experience.
- Core unit + integration tests (P0 test items) passing.

## 6. Testing Focus Checklist (Initial)
- Budget thresholds: 79.9%, 80%, 89.9%, 90%, >90%.
- Forex card: load, multiple expenses, boundary at 20%.
- Rate cache TTL expiry path vs cached path.
- Phase resolution at start/end date edges.
- Editing an expense across currencies (should we allow? if not, validate & reject).
- Deleting earliest vs latest expense recalculations.

## 7. Open Questions
| Question | Proposed Interim Answer |
|----------|------------------------|
| Allow editing currency of an expense? | MVP: No; require delete & recreate (simplifies spent tallies). |
| Timezone handling? | Assume local device timezone; store UTC ISO. |
| Rounding strategy for INR equivalent? | Round to 2 decimals (bankers rounding optional) after multiplication. |
| Category customization? | MVP fixed list from PRD. |

## 8. Next Steps (Immediately Actionable)
1. Execute Phase 1 P0 tasks in sequence T01.01 -> T02.04 -> T03.04 -> T04.02.
2. Lay foundational tests early (T12.01, T12.02) to catch regressions.
3. Implement rate caching before broad expense logging to ensure consistent INR equivalents.

---
Generated from PRD (docs/prd.md) on first pass; refine as tasks progress.
