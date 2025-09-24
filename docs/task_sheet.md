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
| T02.02 | DB | Migration script | P0 | Simple bootstrap migration (idempotent create tables). | T02.01 | Done | Added `db/migrate.py` with `apply_migrations()` calling `init_db()` and recording `schema_version=1` in metadata; idempotency test passes. | Running twice is safe; schema_version stays 1. |
| T02.03 | Models | Pydantic models | P0 | ExpenseIn, ExpenseOut, Budget, ForexCard, RateRecord. | T02.01 | Done | Added `models/` package with constants and Pydantic models (validation for currencies, categories, payment methods, future-date prevention, threshold helpers, low balance). | Validation errors on bad input. |
| T02.04 | DAL | CRUD utilities | P0 | Abstract DB access (insert expense, list, update spent). | T02.02 | Done | Added `db/dal.py` with `Database` class: connect helper, insert/get/list expenses (filters: date range, currency), increment/set budget helpers; smoke tested insert + list + budget spent update. | Insert/select roundtrip integrity. |
| T02.05 | DAL | Aggregation queries | P1 | Helpers for sums by currency, category, date. | T02.04 | Done | Added aggregation methods to `Database`: `daily_totals()`, `sums_by_currency()`, `sums_by_category()` (with percent calc). Smoke tested with sample data. | Correct sums vs manual calc. |

### E3 Budget & Forex Configuration
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T03.01 | Budget | Budget table & seed | P0 | Store max & spent for INR/SGD/MYR. | T02.01 | Done | Added `db/seed.py` with `seed_budgets()` ensuring baseline rows (INR, SGD, MYR) inserted if missing; accepts optional max overrides; idempotent. | Defaults persisted. |
| T03.02 | Budget | Budget update endpoint | P0 | POST/PUT to set/modify max budgets. | T03.01 | Done | Implemented `PUT /budgets/{currency}` in `routers/budgets.py` using `Database.set_budget_max` (upsert via ON CONFLICT). Returns `Budget` model with existing spent_amount preserved. Router registered in `main.py`. Smoke tested INR update (existing spent retained), and creation for SGD & MYR. | PUT with valid currency & positive max updates/creates row; spent_amount unchanged; invalid currency 400; max_amount must be > 0. |
| T03.03 | Budget | Spent auto-update | P0 | Increment spent when expense logged (same currency). | T04.02 | Done | Added atomic DAL method `insert_expense_with_budget` performing expense insert + `budgets.spent_amount` increment in one transaction (ensures consistency). Added docstring referencing T03.03. Smoke tested with two INR expenses (spent_amount increased cumulatively). | Inserting expenses via new method increments spent correctly; failure should rollback both operations. |
| T03.04 | Budget | Remaining calc util | P0 | Helper returns remaining & thresholds (80%, 90%). | T03.03 | Done | Added `list_budgets()` to DAL and new `services/budget_utils.py` with `budget_status`, `get_budget_status`, `list_budget_statuses` returning remaining, percent_used, and 80/90 flags. Smoke tested outputs for INR, SGD, MYR. | Remaining never negative; percent_used accurate; flags flip at 80%, 90%. |

### E4 Expense Logging Core
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T04.01 | Expense | Validation rules | P0 | Validate currency, category, payment method, date range. | T02.03 | Done | Expanded categories per PRD (visa_fees, insurance, forex, sim, other); added cross-field rule (forex payment only for SGD/MYR) via root validator; scaffolded `services/expense_validation.py` for future trip date constraints. Smoke tested valid/invalid cases. | Reject invalid combos incl. forex+INR; category whitelist enforced. |
| T04.02 | Expense | Create endpoint | P0 | POST /expenses creates record & INR equivalent. | T07.03, T04.01 | Done | Added `routers/expenses.py` with POST /expenses using `ExpenseIn` validation + domain hook, stub `RateService` (hardcoded INR per SGD/MYR), and `Database.insert_expense_with_budget` for atomic budget spent increment. Implemented rounding via `services/money.round2`. Smoke tested INR and SGD forex expenses + invalid forex+INR case. | 201 response; fields include id,inr_equivalent,exchange_rate; forex+INR rejected; budget spent increments. |
| T04.03 | Expense | List endpoint | P0 | GET /expenses (filters: date range, currency, phase). | T04.02 | Done | Added GET /expenses with optional start_date, end_date, currency filters returning list[ExpenseOut] ordered (date desc, id desc via DAL). Currency validated; date range ordering enforced; phase param stub returns 400 (not yet supported until timeline tasks). | Filter accuracy across date ranges & currency; invalid currency rejected; phase currently unsupported. |
| T04.04 | Expense | Edit endpoint | P1 | PATCH /expenses/{id} adjust amounts & budgets delta. | T04.02, T03.03 | Done | Implemented `ExpenseUpdateIn` (partial, currency immutable), `update_expense_with_budget` atomic DAL method, and PATCH route recomputing INR & exchange_rate (or 1.0 for INR), applying budget delta = new_amount - old_amount. Validation rejects empty payload. | Editing updates spent_amount by delta; currency change not allowed; empty patch 422; amount/category/description/date/payment_method individually patchable. |
| T04.05 | Expense | Delete endpoint | P1 | DELETE /expenses/{id} reverse budget spent. | T04.02, T03.03 | Done | Added `delete_expense_with_budget` (atomic fetch amount+currency, delete, decrement spent with MAX(0) clamp) and DELETE route returning 204. Smoke tested: spent_amount reduced by expense amount. | Deleting expense decrements spent; non-existent id 404; budget never negative. |

### E5 Timeline Handling
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T05.01 | Timeline | Trip date config | P0 | Store start/end dates in metadata. | T02.01 | Done | Added metadata-backed trip dates: DAL methods `get_trip_dates`/`set_trip_dates`, `TripDates` model (validation end>=start), new `timeline` router with PUT/GET /trip-dates/, registered in app. | Setting trip dates persists ISO dates; GET returns them; end before start rejected (422); missing dates => 404. |
| T05.02 | Timeline | Phase resolver | P0 | Utility: given date -> pre-trip or trip. | T05.01 | Done | Added `services/timeline.resolve_phase(date, trip_dates)` returning 'pre-trip' if before configured start_date else 'trip'. Falls back to 'trip' if dates unset. | Before start -> pre-trip; start day and after -> trip; unset dates default to trip. |
| T05.03 | Timeline | Filter integration | P1 | Phase filter param uses resolver. | T05.02 | Done | Added phase filtering to GET /expenses: phase=pre-trip maps to end_date < trip_start; phase=trip maps to start_date >= trip_start. Option A semantics when trip dates unset (pre-trip -> empty list, trip -> all). Added app factory override for test isolation + smoke test script. | Pre-trip returns only dates before trip start; trip returns on/after start; unset trip dates behave per spec. |

### E6 Forex Card Tracking
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T06.01 | Forex | Schema & model | P0 | Track loaded & spent for SGD/MYR forex cards. | T02.01 | Done | Schema table already existed; confirmed Pydantic `ForexCard` model with currency validation & remaining/low balance helpers. Added DAL methods `get_forex_card` and `list_forex_cards` for retrieval. No mutations yet (handled in T06.02+). | Retrieval returns correct rows; unsupported currency rejected at model layer. |
| T06.02 | Forex | Load/adjust endpoint | P1 | Modify loaded amount. | T06.01 | Done | Added `forex` router with `PUT /forex-cards/{currency}` (upsert semantics) and `GET /forex-cards/` list. DAL method `set_forex_card_loaded` validates non-negative and preserves spent_amount. Auto schema migration on app startup ensures table exists for fresh test DBs. | Create/update SGD/MYR returns 200 with remaining & low_balance flag; unsupported currency 400; negative amount 400. |
| T06.03 | Forex | Deduct on expense | P0 | If paymentMethod=forex: increment spent & available. | T04.02, T06.01 | Done | Extended DAL methods (`insert_expense_with_budget`, `update_expense_with_budget`, `delete_expense_with_budget`) to adjust `forex_cards.spent_amount` for SGD/MYR when payment_method transitions involve 'forex'. Handles create, amount edit, payment method switch (forex<->cash/card), and delete. Smoke script `scripts/smoke_forex_deduction.py` exercises deltas. | Creating forex expense increases forex spent; editing amount updates delta; switching away subtracts prior amount; switching to forex adds amount; delete subtracts. |
| T06.04 | Forex | Low balance alert hook | P1 | Flag when remaining <20%. | T06.03 | Done | Added `services/forex_utils.py` with threshold logic (<20%), extended `ForexCardOut` to include `percent_remaining` and centralized low_balance calc. Router now reuses utility. Smoke script `scripts/smoke_forex_low_balance.py` verifies crossing below then above threshold via expense create/delete. | Alert triggers just below 20%, not at exactly 20%; percent_remaining calculation correct; deleting expense reverses flag. |

### E7 Exchange Rate Integration
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T07.01 | Rates | Config provider choice | P0 | Choose API (ExchangeRate-API or fallback). | T01.03 | Done | Added `exchange_rate_provider` setting (values: static, external-placeholder). Implemented provider abstraction `services/rates/` with `RateProvider` base, `StaticRateProvider`, `ExternalPlaceholderRateProvider`, factory `make_rate_provider`, and `RateServiceFacade` preserving existing compute API. Expenses router now resolves provider from settings. Smoke script `scripts/smoke_rate_provider_switch.py` demonstrates differing rates for SGD between providers. | Switching setting changes exchange_rate & inr_equivalent; unsupported provider rejected; static provider matches previous hardcoded rates. |
| T07.02 | Rates | HTTP client util | P0 | Reusable httpx wrapper with timeout/retry. | T01.04 | Done | Added `services/http_client.py` (stdlib urllib) with retry/backoff and `HttpError`. Implemented `ExternalHTTPRateProvider` in `services/rates/providers.py` using exchangerate.host (base=INR) with 30m cache, graceful fallback to static rates on failure. Added provider id `external-http` to settings validation. Smoke script `scripts/smoke_rate_external_http.py` compares static vs external-http outputs. | API fetch populates rates (INR per quote); network failure falls back to static; cache TTL respected; provider switch changes exchange_rate for non-INR currencies. |
| T07.03 | Rates | Fetch & cache service | P0 | Cache INR-SGD, INR-MYR for 1h. | T07.02 | Done | Implemented `CentralRateCacheService` (`services/rates/cache_service.py`) wrapping underlying provider via existing factory; in-memory dict with global TTL from `rates_cache_ttl_seconds`, singleton via lru_cache; integrated into `expenses` router dependency replacing direct provider instantiation; added smoke script `scripts/smoke_rate_cache.py` demonstrating reuse vs forced refresh. | First call populates cache (timestamps recorded); second call within TTL keeps identical fetched_at; after manual backdate beyond TTL new timestamps appear; rates still resolve when provider is external-http or static. |
| T07.04 | Rates | Manual override endpoint | P1 | POST to set manual rates if API down. | T07.03 | Done | Added manual override layer: extended `CentralRateCacheService` with override store (rate + expiry) precedence over cache; new `rates` router (`routers/rates.py`) with GET /rates/overrides, POST /rates/overrides, DELETE /rates/overrides/{currency}; guarded by `enable_rate_override` setting; smoke script `scripts/smoke_rate_override.py` shows set->use->clear->expiry paths. | Setting override returns new value for compute; clearing reverts to provider/cached; expiry removes entry automatically; invalid (non-positive) rate/ttl rejected; feature disabled returns 403. |
| T07.05 | Rates | INR equivalent calc | P0 | Utility used when logging expenses. | T07.03 | Done | Added centralized `compute_inr_equivalent` in `services/rates/conversion.py` returning immutable result (rate + inr_equivalent) using shared rounding (`round2`), integrated into create & patch expense endpoints (replacing ad-hoc logic). Handles INR passthrough (rate=1.0) and uses cached/override rate service for foreign currencies. | INR currency returns rate=1.0 & identical amount; foreign currency multiplication rounded to 2 decimals; override + cache paths still honored; editing expense recomputes values consistently. |

### E8 Spending Analytics & Metrics
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T08.01 | Analytics | Daily totals query | P0 | Sum INR equivalent per day. | T02.05 | Done | Added `daily_totals` DAL method already existed; introduced `analytics` router with `GET /analytics/daily-totals` returning ascending list of `{date,total_inr}` (Pydantic model `DailyTotal`). Validates start_date<=end_date; leverages centralized rounding from stored `inr_equivalent`. | Date ordering asc; empty list when no expenses; start_date>end_date returns 400; amounts match sum of individual expenses' `inr_equivalent` for each day. |
| T08.02 | Analytics | Average daily spend | P0 | total_spent / days_elapsed. | T08.01, T05.02 | Done | Added DAL helpers `total_inr_spent()` and `earliest_expense_date()`, utility `compute_average_daily_spend` (returns total_inr, days_elapsed inclusive earliest->as_of, average_daily_spend rounded). New endpoint `GET /analytics/average-daily-spend` with optional `as_of` date param. | No expenses -> all zeros; days_elapsed inclusive span; average = sum(inr_equivalent)/days_elapsed with 2-dec rounding; as_of before earliest still zeros; changing data updates average accordingly. |
| T08.03 | Analytics | Remaining daily budget | P0 | (remaining_budget / days_left). | T03.04, T05.02 | Done | Added `compute_remaining_daily_budget` in `services/analytics_utils.py` returning remaining_inr, days_left, remaining_daily_budget (rounded); exposes `GET /analytics/remaining-daily-budget` with optional `as_of` date. Handles missing trip dates and post-trip dates (zeros). | Remaining goes to 0 when budget exhausted; days_left inclusive of as_of & trip_end; last day division returns remaining as per-day value; as_of after trip -> zeros; no trip dates -> zeros. |
| T08.04 | Analytics | Currency breakdown | P1 | Aggregation per currency. | T02.05 | Done | Added `compute_currency_breakdown` producing per-currency (amount_total, inr_total, percent_inr) via DAL `sums_by_currency`; new endpoint `GET /analytics/currency-breakdown` with optional start_date/end_date validation. | Percent sums ~100% (allow rounding drift); empty dataset -> percents 0; date filter correctness; start_date>end_date 400; matches manual sum of expenses.inr_equivalent per currency. |
| T08.05 | Analytics | Category breakdown | P1 | Percent & absolute per category. | T02.05 | Done | Added `CategoryBreakdownItem` dataclass + `compute_category_breakdown` (wraps DAL `sums_by_category` which already computes percent). New endpoint `GET /analytics/category-breakdown` with optional `start_date`/`end_date` filters & validation of range. | Percent sums ~100% (allow 0.01 drift); ordering by highest `inr_total` (DAL); empty dataset -> 0 percents; date filters respected; start_date>end_date 400. |
| T08.06 | Analytics | Trend data endpoint | P1 | Endpoint for chart (daily). | T08.01 | Done | Added `TrendPoint` dataclass + `compute_trend_data` (wraps DAL `daily_totals` and computes cumulative). New endpoint `GET /analytics/trend` with optional start/end date and range validation. | Ordered ascending by date; cumulative monotonic; empty range -> []; start_date>end_date 400; cumulative final value equals sum of daily totals. |

### E9 UI / Templates / UX (Jinja2)
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T09.01 | UI | Base layout template | P0 | Shared head, nav (phase indicator). | T01.01 | Done | Added Jinja2 setup: `templates/base.html` with reusable blocks (title, head_extra, content, scripts) and minimal dark theme styling; nav extracted to `templates/partials/_nav.html` showing current phase chip (pre-trip/trip) resolved via trip dates; new `ui` router with `GET /ui` returning TemplateResponse including phase + version; integrated router in `main.py`. | Blocks extend properly; /ui renders 200 with phase chip reflecting trip dates (defaults to trip if unset). |
| T09.02 | UI | Dashboard template | P0 | Progress bars, top metrics, exchange rates. | T03.04, T08.02 | Done | Added `dashboard.html` extending base with sections: summary cards (avg daily spend, remaining daily budget, exchange rates), budgets progress bars (macro in `_components.html`), currency & category breakdown tables. Updated `/ui` route to compute metrics via existing analytics & budget utilities plus central rate cache. | Correct numbers shown; /ui returns 200; budgets reflect percent_used with color changes at 80/90%. |
| T09.03 | UI | Expense entry form | P0 | Amount, currency picker, category tags, payment method, date picker. | T04.02 | Done | Added `expense_form.html` extending base with required fields (amount, currency, category, payment_method, date, description optional), reusable `_form_errors.html` partial for validation listing, success flash panel showing created expense summary. Added GET `/ui/expenses/new` (blank form) & POST `/ui/expenses/new` (server-side validate via `ExpenseIn` + domain hook, compute INR equivalent via shared rate cache then persist with `insert_expense_with_budget`). Form preserves user inputs on validation errors; clears fields (except date) after success. | Rendering form 200; creating valid expense shows success panel and persists (visible via API/list later); invalid combos (forex + INR, missing required fields, bad date) show error list without creating record; budgets & forex card spent increment after creation. |
| T09.04 | UI | Expense list view | P0 | Group by date, edit/delete actions. | T04.03 | Done | Implemented grouped expenses list (`/ui/expenses`) with date sections (descending), per-day INR total, edit and delete actions. Added edit form reuse of create template (conditional currency immutability) and delete POST endpoint. | Grouping correct (dates desc, items within date id desc), day INR total matches sum of rows, edit updates budgets/forex adjustments, delete decrements budget & forex spent, currency immutable on edit, validation errors surfaced. |
| T09.05 | UI | Analytics view | P1 | Charts placeholders (server-render numeric; charts optional). | T08.05 | Not Started |  | Data consistency vs API. |
| T09.06 | UI | Alerts UI indicators | P1 | Visual cues for 80%,90%, low forex balance. | T03.04, T06.04 | Done | Added alert aggregation in `/ui` route combining budget threshold (>=80%, >=90%) and forex low balance (<20%) into unified list. Implemented `_alerts.html` partial rendering severity-styled rows and nav badge showing count. Dashboard now includes Alerts section above budgets. | Trigger budgets at 79.9/80/89.9/90 boundaries (appearance shifts warn→danger). Forex card remaining exactly 20% no alert; below 20% shows alert. Multiple alerts list order (budget then forex). Nav badge hides when count=0. |
| T09.07 | UI | Mobile responsiveness | P1 | Flex/grid tweaks for small screens. | T09.02 | Done | Added responsive nav (wrapping links, reduced gaps), mobile card view for expenses (table hidden <640px), adjusted dashboard grids (tighter gaps), ensured analytics tables scroll with existing overflow rules, and added minor CSS tweaks for headings/table text on small screens. | On narrow viewport (<640px) no horizontal scroll for nav/dashboard; expenses show stacked cards; switching above/below breakpoint toggles table vs cards; alert & badge layout wraps without overlap. |
| T09.08 | UI | Accessibility pass | P2 | Labels, aria, contrast. | T09.07 | Not Started |  | Lighthouse a11y score. |
| T09.09 | UI | Settings page (trip, thresholds, forex) | P1 | Manage trip dates, dynamic alert thresholds, and forex card loads via unified UI. | T05.01, T10.01, T10.02 | Done | Added `/ui/settings` GET/POST, `settings.html` template with three forms (trip dates, thresholds, forex loads); integrated dynamic thresholds service; nav link added. | Form submissions persist metadata & forex loads, thresholds reflect in alerts immediately. |

### E10 Alerts & Threshold Logic
| ID | Task | Sub Task | Priority | Description | Dependencies | Status | What Was Done | What Should Be Tested |
|----|------|----------|----------|-------------|--------------|--------|---------------|-----------------------|
| T10.01 | Alerts | Budget threshold logic | P0 | 80%, 90% flags from budget util. | T03.04 | Done | Implemented via existing `services/budget_utils.py` (`budget_status` exposes `eighty`/`ninety` flags) already consumed on dashboard; added dedicated `/ui/budgets` page (progress bars + legend) reusing macro `_components.html::progress_bar` with color transitions (blue/amber/red) to visualize <80%, >=80%<90%, >=90%. | Trigger at correct boundaries (79.9 no flag, 80 amber, 89.99 amber, 90 red). |
| T10.02 | Alerts | Forex low balance logic | P1 | <20% remaining flag. | T06.04 | Done | Centralized in `services/forex_utils.py` (`LOW_BALANCE_THRESHOLD=0.20`, `card_status` sets `low_balance` when remaining/loaded < 20%). Added `/ui/forex` page listing cards with Low badge (red) vs OK (green) and summary counts; nav badge shows count via alerts_count. | Edge at exactly 20% shows OK (not low); just below triggers Low; multiple cards aggregate correctly. |
| T10.03 | Alerts | Aggregation surface | P1 | Provide list of active alerts to UI. | T10.01 | Done | Added `services/alerts.py` with `collect_alerts()` consolidating budget threshold (>=80/90) and forex low balance (<20%) logic into unified list consumed by dashboard and new `/ui/alerts` page. Refactored `/ui` route to use service; created `alerts.html` reusing `_alerts.html` partial and added nav link. | Multiple alerts display with proper severity ordering; dashboard & alerts page show identical set. |

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
