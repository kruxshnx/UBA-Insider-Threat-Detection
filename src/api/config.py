"""
Unified API Settings.
Reads from config.yaml via the central Config singleton, with environment variable overrides.
"""

import os
from typing import List

# Import the central YAML config
try:
    from src.utils.config import config as yaml_config
except ImportError:
    yaml_config = None


def _env_list(key: str, default: List[str]) -> List[str]:
    """Read a comma-separated env var into a list, or return default."""
    val = os.environ.get(key)
    if val:
        return [v.strip() for v in val.split(",") if v.strip()]
    return default


class Settings:
    """API settings unified from config.yaml + environment overrides."""

    # ── Paths ────────────────────────────────────────────────────────────────
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
    RISK_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data/risk_output")
    PROCESSED_DATA_DIR = os.path.join(PROJECT_ROOT, "data/processed")
    MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
    SECURITY_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data/security_output")
    RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data/raw")
    FEEDBACK_DIR = os.path.join(PROJECT_ROOT, "data")

    # ── API Metadata ─────────────────────────────────────────────────────────
    _api_cfg = yaml_config.api if yaml_config else {}

    API_TITLE: str = os.environ.get(
        "UBA_API_TITLE",
        _api_cfg.get("title", "UBA ITD API"),
    )
    API_VERSION: str = os.environ.get(
        "UBA_API_VERSION",
        _api_cfg.get("version", "2.1.0"),
    )
    API_DESCRIPTION: str = (
        "User Behavior Analytics & Insider Threat Detection API — "
        "Role-based models · Behavioral features · MITRE ATT&CK mapping · "
        "Explainability · Rate limiting · Audit logging"
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = _env_list(
        "UBA_CORS_ORIGINS",
        _api_cfg.get("cors_origins", [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
        ]),
    )

    # ── Rate Limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = int(
        os.environ.get("UBA_RATE_LIMIT_REQUESTS",
                       _api_cfg.get("rate_limit_requests", 100))
    )
    RATE_LIMIT_WINDOW_SECONDS: int = int(
        os.environ.get("UBA_RATE_LIMIT_WINDOW",
                       _api_cfg.get("rate_limit_window_seconds", 60))
    )

    # ── Data Cache ───────────────────────────────────────────────────────────
    DATA_CACHE_TTL_SECONDS: int = int(
        os.environ.get("UBA_CACHE_TTL", 30)
    )

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.environ.get("UBA_LOG_LEVEL", "INFO")


settings = Settings()
