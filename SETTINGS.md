# Runtime Settings Extensions

This document describes the additional runtime-configurable settings exposed via `/ui/settings`.

## Sections

### 1. Rate Provider & Cache
- **Provider** (`exchange_rate_provider_override`)  
  Values: `static`, `external-placeholder`, `external-http`  
  Overrides the environment `exchange_rate_provider`.
- **Cache TTL (seconds)** (`rates_cache_ttl`)  
  Range: 60–86400. Overrides `rates_cache_ttl_seconds` from environment.

Applied dynamically when the central cache service is (re)created. The legacy singleton keeps prior values until restart; use a dynamic factory if needed for immediate effect.

### 2. Budget Settings
- **Enforce Cap** (`budget_enforce_cap`)  
  When enabled, inserting or increasing an expense that would exceed `budgets.max_amount` raises an error.
- **Auto-Create Budgets** (`budget_auto_create`)  
  When enabled, missing budget rows are created automatically with max=0 or a default.
- **Default Budget Amounts** (`default_budget_amounts`)  
  JSON map storing per-currency default max budgets. The UI saves individual entries as they are provided.

### 3. UI Preferences
- **Theme** (`ui_theme`) values: `auto|light|dark`
- **Expense Layout** (`ui_expense_layout`) values: `detailed|compact`
- **Show Day Totals** (`ui_show_day_totals`) boolean
- **Widget Toggles** (`widget_show_budgets`, `widget_show_rates`, `widget_show_categories`, `widget_show_currencies`) booleans controlling dashboard component visibility.

## Metadata Storage
All settings persist in the `metadata` table. Upserts use an `INSERT ... ON CONFLICT` pattern with `updated_at` timestamp updates.

## Error Handling
- Invalid numeric/enum inputs are validated server-side and surfaced in the UI section error list.
- Budget cap violations surface as `ValueError` messages during expense insertion or update.

## Extensibility
Add new keys by:  
1. Creating typed accessor in `app/services/app_settings.py`.  
2. Surfacing value in `ui_settings` GET context.  
3. Adding a `<form>` section posting `section=<name>` in `settings.html` and handling it in the POST router.

## Notes
- The cached rate service (`get_central_rate_cache_service`) still reflects the provider/TTL at process start. Use `build_dynamic_rate_cache_service(db)` if you need to immediately apply changed values in a one-off context.
- Existing alert threshold and forex load logic unchanged.
