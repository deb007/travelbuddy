from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, AnyHttpUrl


class Settings(BaseSettings):
    """Application settings loaded from environment with defaults.

    Environment variable mapping follows pydantic's rules (e.g., APP_NAME, DEBUG, DATA_DIR, DB_FILENAME, RATES_CACHE_TTL_SECONDS).
    """

    # Basic app metadata
    app_name: str = "Travel Expense Tracker"
    debug: bool = True
    version: str = "0.1.0"

    # Data & persistence
    data_dir: Path = Path("data")
    db_filename: str = "app.sqlite3"
    db_path: Optional[Path] = None  # derived if not provided

    # Exchange rates / caching
    rates_cache_ttl_seconds: int = 3600  # 1 hour
    exchange_api_base_url: AnyHttpUrl = "https://api.exchangerate-api.com/v4/latest"  # placeholder; final path may append base currency
    http_timeout_seconds: float = 5.0

    # Exchange rate provider (T07.01)
    # Allowed: 'static' (built-in fixed placeholders), 'external-placeholder' (hook for future real API)
    exchange_rate_provider: str = "static"

    # Feature toggles / future
    enable_rate_override: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

    def init_post_load(self) -> None:
        """Finalize derived fields and ensure directories exist."""
        if self.db_path is None:
            self.db_path = self.data_dir / self.db_filename
        # Ensure persistence directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Normalize / validate provider
        allowed = {"static", "external-placeholder", "external-http"}
        if self.exchange_rate_provider not in allowed:
            raise ValueError(
                f"Unsupported exchange_rate_provider '{self.exchange_rate_provider}'. Allowed: {allowed}"
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.init_post_load()
    return settings
