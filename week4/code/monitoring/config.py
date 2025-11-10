import os
from dataclasses import dataclass


def _to_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    logs_dir: str = os.environ.get("LOGS_DIR", "logs")
    database_url: str | None = os.environ.get("DATABASE_URL")
    processed_prefix: str = os.environ.get("PROCESSED_PREFIX", "_")
    file_glob: str = os.environ.get("LOG_FILE_GLOB", "*.json")
    poll_seconds: float = float(os.environ.get("POLL_SECONDS", "2"))
    debug: bool = _to_bool(os.environ.get("MONITORING_DEBUG") or os.environ.get("DEBUG"), False)


def get_settings() -> Settings:
    return Settings()
