"""
UBA & Insider Threat Detection — FastAPI Backend v2.1

Features:
  • Structured logging with request-ID correlation
  • Startup / shutdown lifecycle hooks
  • Rate limiting middleware with audit trail
  • Response-time header on every request
  • Global exception handler (consistent JSON errors)
  • Lightweight RBAC via X-User-Role header
  • Comprehensive API metadata for /docs
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict
from collections import defaultdict
import logging
import time
import uuid
import os

from src.api.config import settings
# RBAC helpers re-exported for backwards compatibility (see security.py).
from src.api.security import VALID_ROLES, get_current_role, require_role
from src.api.routers import users, events, stats, analysis, timeline, alerts, models, telemetry

__all__ = ["app", "VALID_ROLES", "get_current_role", "require_role"]

# =============================================================================
# LOGGING SETUP
# =============================================================================
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("uba.api")


# =============================================================================
# RATE LIMITING
# =============================================================================
class RateLimiter:
    """Sliding-window in-memory rate limiter."""

    def __init__(self, requests_per_window: int = 100, window_seconds: int = 60):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        self.requests[client_id] = [
            ts for ts in self.requests[client_id] if ts > window_start
        ]
        if len(self.requests[client_id]) >= self.requests_per_window:
            return False
        self.requests[client_id].append(now)
        return True

    def get_remaining(self, client_id: str) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        current = len([ts for ts in self.requests[client_id] if ts > window_start])
        return max(0, self.requests_per_window - current)


# =============================================================================
# AUDIT LOGGING
# =============================================================================
class AuditLogger:
    """Append-only file logger for API access auditing."""

    def __init__(self, log_dir: str = None):
        self.log_dir = log_dir or settings.SECURITY_OUTPUT_DIR
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "api_audit.log")

    def log(
        self,
        request: Request,
        response_status: int,
        request_id: str = "-",
        user_role: str = "anonymous",
    ):
        entry = (
            f"{datetime.now().isoformat()} | "
            f"{request_id} | "
            f"{request.client.host if request.client else 'unknown'} | "
            f"{request.method} {request.url.path} | "
            f"{response_status} | "
            f"{user_role}\n"
        )
        try:
            # utf-8 + errors="replace" so non-ASCII paths/roles can't raise a
            # UnicodeEncodeError under Windows' default cp1252 console codec.
            with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(entry)
        except Exception:
            pass  # Never crash on audit-log I/O


# =============================================================================
# RBAC DEPENDENCY (DEMO CONTROL)
# =============================================================================
# RBAC is enforced via the `X-User-Role` request header. This is a DEMO-ONLY
# control: the header is client-supplied and therefore SPOOFABLE — any caller
# can send `X-User-Role: Admin`. In production, replace it with a server-side
# authenticated identity (signed JWT/OIDC/SSO) from which the role is derived.
# The helpers (`get_current_role`, `require_role`, `VALID_ROLES`) now live in
# `src.api.security` so routers can guard endpoints without importing `main`
# and causing a circular import. They are re-exported here for backwards
# compatibility with existing references.


# =============================================================================
# APP INITIALIZATION
# =============================================================================
TAGS_METADATA = [
    {"name": "Health", "description": "Service health & readiness probes"},
    {"name": "Stats", "description": "Aggregate system statistics and dashboard summary"},
    {"name": "Users", "description": "User risk profiles and individual user details"},
    {"name": "Events", "description": "Risk-scored event stream"},
    {"name": "Analysis", "description": "Per-user risk history, SHAP explanations, and feedback"},
    {"name": "Timeline", "description": "Chronological event timeline per user"},
    {"name": "Alerts", "description": "Security alerts with severity filtering and pagination"},
    {"name": "Models", "description": "ML model health and metadata"},
    {"name": "Admin", "description": "Administrative operations (cache, config)"},
]


# =============================================================================
# LIFESPAN (replaces deprecated on_event)
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the application."""
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  UBA ITD API v%s starting up", settings.API_VERSION)
    logger.info("  Log level : %s", settings.LOG_LEVEL)
    logger.info("  CORS      : %s", settings.CORS_ORIGINS)
    logger.info("  Rate limit: %d req / %ds window", settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW_SECONDS)
    logger.info("  Cache TTL : %ds", settings.DATA_CACHE_TTL_SECONDS)
    logger.info("=" * 60)

    for name, path in [
        ("Risk output", settings.RISK_OUTPUT_DIR),
        ("Processed data", settings.PROCESSED_DATA_DIR),
        ("Models", settings.MODELS_DIR),
    ]:
        if os.path.isdir(path):
            logger.info("  + %s: %s", name, path)
        else:
            logger.warning("  - %s directory missing: %s", name, path)

    # Initialise the users table (replaces the deprecated router on_event).
    try:
        from src.api.routers.users import ensure_users_table
        ensure_users_table()
        logger.info("  + Users table ready")
    except Exception as e:
        logger.warning("  - Users table init failed: %s", e)

    try:
        from src.api.services.data_loader import data_loader
        data_loader.get_system_stats()
        logger.info("  + Data cache warmed")
    except Exception as e:
        logger.warning("  - Cache warm-up failed: %s", e)

    yield  # ── Application runs here ─────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("UBA ITD API shutting down gracefully.")


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=TAGS_METADATA,
    contact={"name": "UBA ITD Team"},
    license_info={"name": "Internal Use"},
    lifespan=lifespan,
)

rate_limiter = RateLimiter(
    settings.RATE_LIMIT_REQUESTS,
    settings.RATE_LIMIT_WINDOW_SECONDS,
)
audit_logger = AuditLogger()


# =============================================================================
# MIDDLEWARE
# =============================================================================
@app.middleware("http")
async def request_lifecycle_middleware(request: Request, call_next):
    """
    Combined middleware that handles, in order:
      1. Request-ID generation
      2. Rate limiting
      3. Response timing
      4. Audit logging
    """
    # 1. Request ID
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    # 2. Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        audit_logger.log(request, 429, request_id)
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded. Try again later.", "status_code": 429},
            headers={
                "Retry-After": str(settings.RATE_LIMIT_WINDOW_SECONDS),
                "X-Request-ID": request_id,
            },
        )

    # 3. Call downstream + time it
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    # 4. Attach headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
    response.headers["X-RateLimit-Remaining"] = str(rate_limiter.get_remaining(client_ip))
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)

    # 5. Audit log
    audit_logger.log(request, response.status_code, request_id)

    # 6. Access log
    logger.info(
        "%s %s %s %dms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )

    return response


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time", "X-RateLimit-Remaining", "X-RateLimit-Limit"],
)


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler returning consistent JSON error envelopes."""
    request_id = getattr(request.state, "request_id", "-")

    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        detail = exc.detail
    else:
        status_code = 500
        detail = "An unexpected error occurred."
        logger.exception("Unhandled exception [%s]: %s", request_id, exc)

    audit_logger.log(request, status_code, request_id)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "Internal Server Error" if status_code == 500 else "Request Error",
            "detail": detail,
            "status_code": status_code,
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


# Lifecycle events are handled by the lifespan context manager defined above.


# =============================================================================
# ROUTERS
# =============================================================================
app.include_router(stats.router, prefix="/api", tags=["Stats"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(events.router, prefix="/api", tags=["Events"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(timeline.router, prefix="/api", tags=["Timeline"])
app.include_router(alerts.router, prefix="/api", tags=["Alerts"])
app.include_router(models.router, prefix="/api", tags=["Models"])
app.include_router(telemetry.router, prefix="/api", tags=["Telemetry"])


# =============================================================================
# ROOT / HEALTH ENDPOINTS
# =============================================================================
FEATURE_LIST = [
    "role_based_models",
    "behavioral_features",
    "mitre_attack_mapping",
    "alert_fatigue_control",
    "shap_explainability",
    "rate_limiting",
    "audit_logging",
    "request_correlation",
    "data_caching",
]


@app.get("/", tags=["Health"])
def read_root():
    """Quick liveness probe."""
    return {
        "status": "online",
        "service": "UBA ITD Risk Engine",
        "version": settings.API_VERSION,
        "features": FEATURE_LIST,
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Detailed readiness probe with system status."""
    return {
        "status": "healthy",
        "service": settings.API_TITLE,
        "version": settings.API_VERSION,
        "timestamp": datetime.now().isoformat(),
        "features": FEATURE_LIST,
        "rate_limit": {
            "max_requests": settings.RATE_LIMIT_REQUESTS,
            "window_seconds": settings.RATE_LIMIT_WINDOW_SECONDS,
        },
    }


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================
@app.post("/api/admin/cache/clear", tags=["Admin"], dependencies=[Depends(require_role("Admin"))])
def clear_cache():
    """Invalidate the in-memory data cache. Requires Admin role."""
    try:
        from src.api.services.data_loader import data_loader
        data_loader.clear_cache()
        logger.info("Data cache cleared by admin.")
        return {"status": "success", "message": "Data cache cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENTRYPOINT
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
