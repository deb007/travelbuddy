"""Generic application settings backed by metadata table.

Provides typed accessors for new configurable settings without duplicating
threshold logic. All functions are resilient: if a key is missing or invalid,
fall back to sensible defaults.

Metadata keys introduced:
  - exchange_rate_provider_override: str in {static, external-placeholder, external-http}
  - rates_cache_ttl: int (seconds, 60..86400)
  - budget_enforce_cap: bool (0/1)
  - budget_auto_create: bool (0/1)
  - default_budget_amounts: JSON object {"INR": 50000, ...}
  - ui_theme: str in {light,dark,auto}
  - ui_show_day_totals: bool
  - ui_expense_layout: str in {compact,detailed}
  - widget_show_budgets / widget_show_rates / widget_show_categories / widget_show_currencies: bool

NOTE: We centralize JSON parsing to avoid scattering try/except blocks.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
import json

from typing import TYPE_CHECKING, Protocol
from app.core.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    pass  # Database type not required directly; duck-typed via _DBConnProto


class _DBConnProto(Protocol):  # minimal protocol to satisfy type checking
    def _connect(self): ...  # noqa: D401


ALLOWED_RATE_PROVIDERS = {"static", "external-placeholder", "external-http"}
DEFAULT_THEME = "auto"
DEFAULT_EXPENSE_LAYOUT = "detailed"

# ------------- Low level helpers -----------------


def _get_metadata_value(db: _DBConnProto, key: str) -> Optional[str]:
    with db._connect() as conn:  # type: ignore[attr-defined]
        cur = conn.cursor()
        cur.execute("SELECT value FROM metadata WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None


def _set_metadata_value(db: _DBConnProto, key: str, value: str) -> None:
    with db._connect() as conn:  # type: ignore[attr-defined]
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (key, value),
        )


def _get_bool(db: _DBConnProto, key: str, default: bool = False) -> bool:
    val = _get_metadata_value(db, key)
    if val is None:
        return default
    return val in ("1", "true", "True", "yes", "on")


def _get_int(
    db: _DBConnProto,
    key: str,
    default: int,
    min_v: int | None = None,
    max_v: int | None = None,
) -> int:
    val = _get_metadata_value(db, key)
    if val is None:
        return default
    try:
        iv = int(val)
        if min_v is not None:
            iv = max(min_v, iv)
        if max_v is not None:
            iv = min(max_v, iv)
        return iv
    except Exception:
        return default


def _get_json_obj(db: _DBConnProto, key: str) -> Dict[str, Any]:
    val = _get_metadata_value(db, key)
    if not val:
        return {}
    try:
        obj = json.loads(val)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _set_json_obj(db: _DBConnProto, key: str, obj: Dict[str, Any]) -> None:
    _set_metadata_value(db, key, json.dumps(obj, separators=(",", ":")))


# ------------- Rate provider / cache -------------


def get_effective_rate_provider(db: _DBConnProto) -> str:
    override = _get_metadata_value(db, "exchange_rate_provider_override")
    if override and override in ALLOWED_RATE_PROVIDERS:
        return override
    # Fall back to environment settings
    return get_settings().exchange_rate_provider


def set_rate_provider(db: _DBConnProto, provider: str) -> None:
    if provider not in ALLOWED_RATE_PROVIDERS:
        raise ValueError(f"Unsupported provider '{provider}'")
    _set_metadata_value(db, "exchange_rate_provider_override", provider)


def get_rates_cache_ttl(db: _DBConnProto) -> int:
    # default from environment settings
    default = get_settings().rates_cache_ttl_seconds
    return _get_int(db, "rates_cache_ttl", default, 60, 86400)


def set_rates_cache_ttl(db: _DBConnProto, ttl_seconds: int) -> None:
    if not (60 <= ttl_seconds <= 86400):
        raise ValueError("TTL must be between 60 and 86400 seconds")
    _set_metadata_value(db, "rates_cache_ttl", str(ttl_seconds))


# ------------- Budget settings -------------------


def get_budget_enforce_cap(db: _DBConnProto) -> bool:
    return _get_bool(db, "budget_enforce_cap", False)


def set_budget_enforce_cap(db: _DBConnProto, value: bool) -> None:
    _set_metadata_value(db, "budget_enforce_cap", "1" if value else "0")


def get_budget_auto_create(db: _DBConnProto) -> bool:
    return _get_bool(db, "budget_auto_create", True)


def set_budget_auto_create(db: _DBConnProto, value: bool) -> None:
    _set_metadata_value(db, "budget_auto_create", "1" if value else "0")


def get_default_budget_amounts(db: _DBConnProto) -> Dict[str, float]:
    obj = _get_json_obj(db, "default_budget_amounts")
    # Ensure float coercion
    return {k: float(v) for k, v in obj.items() if isinstance(v, (int, float))}


def set_default_budget_amount(db: _DBConnProto, currency: str, amount: float) -> None:
    if amount < 0:
        raise ValueError("Default budget cannot be negative")
    cur_map = get_default_budget_amounts(db)
    cur_map[currency.upper()] = float(amount)
    _set_json_obj(db, "default_budget_amounts", cur_map)


# ------------- UI presentation -------------------


def get_ui_theme(db: _DBConnProto) -> str:
    theme = _get_metadata_value(db, "ui_theme") or DEFAULT_THEME
    return theme if theme in {"light", "dark", "auto"} else DEFAULT_THEME


def set_ui_theme(db: _DBConnProto, theme: str) -> None:
    if theme not in {"light", "dark", "auto"}:
        raise ValueError("Invalid theme")
    _set_metadata_value(db, "ui_theme", theme)


def get_ui_show_day_totals(db: _DBConnProto) -> bool:
    return _get_bool(db, "ui_show_day_totals", True)


def set_ui_show_day_totals(db: _DBConnProto, value: bool) -> None:
    _set_metadata_value(db, "ui_show_day_totals", "1" if value else "0")


def get_ui_expense_layout(db: _DBConnProto) -> str:
    layout = _get_metadata_value(db, "ui_expense_layout") or DEFAULT_EXPENSE_LAYOUT
    return layout if layout in {"compact", "detailed"} else DEFAULT_EXPENSE_LAYOUT


def set_ui_expense_layout(db: _DBConnProto, layout: str) -> None:
    if layout not in {"compact", "detailed"}:
        raise ValueError("Invalid layout")
    _set_metadata_value(db, "ui_expense_layout", layout)


def get_widget_flag(db: _DBConnProto, widget: str, default: bool = True) -> bool:
    return _get_bool(db, f"widget_show_{widget}", default)


def set_widget_flag(db: _DBConnProto, widget: str, value: bool) -> None:
    _set_metadata_value(db, f"widget_show_{widget}", "1" if value else "0")


__all__ = [
    # Rate provider
    "get_effective_rate_provider",
    "set_rate_provider",
    "get_rates_cache_ttl",
    "set_rates_cache_ttl",
    # Budget
    "get_budget_enforce_cap",
    "set_budget_enforce_cap",
    "get_budget_auto_create",
    "set_budget_auto_create",
    "get_default_budget_amounts",
    "set_default_budget_amount",
    # UI
    "get_ui_theme",
    "set_ui_theme",
    "get_ui_show_day_totals",
    "set_ui_show_day_totals",
    "get_ui_expense_layout",
    "set_ui_expense_layout",
    "get_widget_flag",
    "set_widget_flag",
]
