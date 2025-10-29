# TravelBuddy Multi-Trip Support — Task Sheet

## Objectives
- Support multiple independent trips with isolated expenses, budgets, forex cards, and analytics.
- Allow users to view historical trips, switch active trip context, and manage trip lifecycle (create, edit, close).
- Preserve existing global configuration semantics (thresholds, rate settings, UI prefs) while scoping operational data per trip.

## Current Constraints
- Single trip assumption baked into schema (`budgets`, `forex_cards`, `expenses` lack `trip_id`; trip dates stored in metadata).
- Services and routers read/write shared tables without trip scoping.
- Reset utilities wipe all transactional data rather than trip-specific slices.
- UI displays single trip data and has no affordance to select or view past trips.

## Key Design Decisions
- Introduce `trips` table (`id`, `name`, `start_date`, `end_date`, `status`, `created_at`, `updated_at`).
- Store active trip id in metadata (`active_trip_id`); add helper service to resolve current trip context for API/UI.
- Add `trip_id` foreign keys (non-null) to `expenses`, `budgets`, `forex_cards`; adjust primary keys (e.g., composite `(trip_id, currency)` for budgets/forex).
- Migrate legacy single-trip data by creating a default trip record and rebasing existing rows during schema upgrade (schema version 2).
- Keep metadata table for global settings; create `trip_settings` key-value table only for trip-scoped metadata if later needed (optional stretch).

## Task Breakdown
| ID | Task | Description | Dependencies | Notes |
|----|------|-------------|--------------|-------|
| MT1.1 | Schema: trips table | Create `trips` table with lifecycle columns and indexes. Seed default row when empty. | — | Ensure timestamps default to UTC ISO strings. |
| MT1.2 | Schema: expenses FK | Add `trip_id` column to `expenses`, backfill via migration, enforce FK. | MT1.1 | Requires temp table copy due to SQLite constraints. |
| MT1.3 | Schema: budgets FK | Replace `budgets` with `(trip_id, currency)` PK, migrate existing rows. | MT1.1 | Preserve `max_amount`/`spent_amount`; seed three currencies per trip. |
| MT1.4 | Schema: forex FK | Mirror MT1.3 for `forex_cards`. | MT1.1 | Maintain unique `(trip_id, currency)`. |
| MT1.5 | Schema: metadata cleanup | Remove `trip_start_date`/`trip_end_date` keys; define `active_trip_id` metadata. | MT1.1 | Backfill `trips.start_date/end_date` using legacy metadata if present. |
| MT1.6 | Migration orchestration | Bump schema version, implement reversible migration script with backup safeguards. | MT1.1–MT1.5 | Add smoke script to verify upgrade path on sample DB. |
| MT2.1 | DAL: trip CRUD | Add methods for create/update/list/get/activate trips, plus helpers to fetch active trip context. | MT1.* | Provide transactional operations. |
| MT2.2 | DAL: scoped data ops | Update budget, expense, forex DAL methods to require `trip_id`; ensure filters default to active trip. | MT2.1 | Adjust signatures and update callers. |
| MT2.3 | DAL: reporting filters | Extend aggregation helpers (totals, sums, timeline) to accept optional `trip_id`. | MT2.2 | Maintain backwards compatibility for historical exports. |
| MT2.4 | Services: context resolver | Introduce service module to cache/resolve active trip and expose convenience accessors. | MT2.1 | Consider request-level cache for FastAPI dependencies. |
| MT2.5 | Services: timeline & reset | Update timeline, analytics, alerts, app_settings, reset utilities to honor trip scope. | MT2.2 | Reset should target a single trip by default, with explicit "wipe all" option. |
| MT3.1 | API: trips router | Expose REST endpoints for listing, creating, updating, activating, archiving trips. | MT2.1 | Include validation (date ranges, unique names). |
| MT3.2 | API: existing routers | Add `trip_id` query/header or use active trip dependency for budgets, expenses, forex, analytics. | MT2.2 | Maintain backwards-compatible defaults via active trip resolution. |
| MT3.3 | API: timeline endpoints | Replace `/trip-dates` with trip-aware endpoints (per trip retrieval/update). | MT3.2 | Provide migration shim or versioned route if needed. |
| MT4.1 | UI: trip selector | Add global trip picker (nav dropdown) showing active trip and quick switch. | MT3.1 | Persist selection (metadata or session). |
| MT4.2 | UI: trip management views | Build pages/modals to create, edit, archive trips and surface status/history. | MT4.1 | Reuse FastAPI templates; ensure validation feedback. |
| MT4.3 | UI: dashboards | Scope dashboard widgets, budgets, expenses, analytics to selected trip. | MT3.2 | Add empty states when trip has no data. |
| MT4.4 | UI: settings | Split settings into trip-scoped vs global sections; update forms to include trip context. | MT3.2 | Clarify which toggles apply across all trips. |
| MT4.5 | UI: historical view | Provide read-only summaries for completed trips (key metrics, export link). | MT4.2 | Consider pagination or collapsible list. |
| MT5.1 | Reset flows | Update reset utilities to operate per trip; expose UI/API controls for reset vs archive. | MT2.5 | Confirm data retention expectations. |
| MT5.2 | Data export (optional) | Add CSV/JSON export per trip for manual backups. | MT4.5 | Stretch goal if time allows. |
| MT6.1 | Tests: migration | Create regression test covering migration path from v1 schema to multi-trip schema. | MT1.* | Include both empty and populated DB fixtures. |
| MT6.2 | Tests: DAL/services | Add unit tests for new DAL trip functions and scoped analytics. | MT2.* | Utilize temp SQLite databases. |
| MT6.3 | Tests: API integration | Expand smoke/integration tests for multi-trip flows (create trip, switch, CRUD expenses). | MT3.* | Update existing scripts (e.g., `scripts/test_phase_filter.py`). |
| MT6.4 | Tests: UI smoke | Ensure templates render for trip picker/management; add selenium-lite manual checklist. | MT4.* | Light-weight due to lack of automated browser tests. |
| MT7.1 | Documentation | Update README, SETTINGS, PRD notes to describe multi-trip support and migration steps. | All | Include upgrade guide with backup instructions. |

## Migration & Rollout Strategy
- Take SQLite backup prior to applying schema migration (documented in README and release notes).
- Ship automated migration (schema version 2) triggered at app startup; detect and populate default trip using legacy metadata.
- Provide post-migration validation script (CLI or script) summarizing trips and counts to confirm success.
- Communicate breaking changes (e.g., deprecated `/trip-dates` endpoint) and offer compatibility window if required.

## Test Plan Highlights
- Migration test ensures legacy DB with expenses/budgets/forex data transitions cleanly and retains totals per trip.
- Unit tests for trip activation logic verifying fallback when metadata missing or trip archived.
- Integration tests covering: creating second trip, switching active trip, verifying isolation of expenses and alerts.
- Manual UI walkthrough: switching trips updates dashboards, historical view accessible, error handling for invalid trip IDs.

## Risks & Mitigations
- **Migration failure**: Build dry-run mode and backup instructions; add automated verification script.  
- **Cross-trip leakage**: Enforce trip scoping at DAL layer and add regression tests for each API surface.  
- **Legacy client breakage**: Document API changes; maintain temporary compatibility routes if necessary.  
- **Performance**: Add indexes on `(trip_id, date)` for expenses to keep queries fast.  
- **User confusion**: Update UX copy to clarify global vs trip-specific settings; provide onboarding banner after upgrade.

## Open Questions
- Should trips support soft delete vs archive state? (Impacts filters and UI display.)
- Do budgets auto-clone when creating a new trip, or start at zero? (Consider settings-driven default budgets.)
- How should active trip selection persist across devices (per user vs global)? Current metadata approach is app-wide.

