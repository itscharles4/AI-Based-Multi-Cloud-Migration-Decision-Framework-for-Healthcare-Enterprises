"""
backend/app.py
==============
Main FastAPI application — production-grade entry point.

Startup sequence:
  1. Connect to Redis
  2. Connect to PostgreSQL + create tables
  3. Register all routers
  4. Add CORS, compression, and request-timing middleware

Run locally:
  uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

Production (Docker):
  uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 4
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.core.config       import settings
from backend.core.database     import init_db, close_db
from backend.core.redis_client import init_redis, close_redis

# Routers
from backend.routers.auth    import router as auth_router
from backend.routers.ingest  import router as ingest_router
from backend.routers.history import router as history_router
from backend.routers.admin   import router as admin_router
from backend.routers.health  import router as health_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup + shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise and clean up resources around the app lifecycle."""
    logger.info("=" * 60)
    logger.info("  %s v%s — %s", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    logger.info("=" * 60)

    # Startup
    logger.info("[startup] Connecting to Redis...")
    await init_redis()

    logger.info("[startup] Connecting to PostgreSQL...")
    await init_db()

    logger.info("[startup] Ready to serve requests ✓")
    yield

    # Shutdown
    logger.info("[shutdown] Closing connections...")
    await close_db()
    await close_redis()
    logger.info("[shutdown] Clean shutdown complete")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## AI-Based Telemedicine Workload Offloader API

**Production-grade** REST API for intelligent IoMT data routing.

### Architecture
- **Layer 1 — Prediction:** LSTM forecasts network latency 30s ahead
- **Layer 2 — Decision:** AHP multi-criteria routing (EDGE vs CLOUD)
- **Layer 3 — Execution:** Async PostgreSQL + real Telegram/Email alerts

### Authentication
All endpoints (except `/health`, `/ready`, `/metrics`) require a **Bearer JWT token**.
Obtain tokens via `POST /auth/login`.

### Roles
| Role | Access |
|------|--------|
| `auditor` | Read-only: history, stats, audit log, CSV export |
| `doctor`  | Auditor + ingest pipeline |
| `admin`   | Doctor + user management |

### Quick Start
1. Register: `POST /auth/register`
2. Login: `POST /auth/login` → get `access_token`
3. Ingest: `POST /ingest` with `Authorization: Bearer <token>`
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Add X-Process-Time header and log slow requests."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed  = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed:.1f}"
    if elapsed > 1000:
        logger.warning("[slow-request] %s %s took %.0fms", request.method, request.url.path, elapsed)
    return response


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("[unhandled] %s %s → %s: %s",
                 request.method, request.url.path, type(exc).__name__, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc) if settings.DEBUG else ""},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router)          # /health  /ready  /metrics
app.include_router(auth_router)            # /auth/*
app.include_router(ingest_router)          # /ingest
app.include_router(history_router)         # /stats  /history  /devices  /audit  /export
app.include_router(admin_router)           # /admin/*


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {
        "name":        settings.APP_NAME,
        "version":     settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs":        "/docs",
        "health":      "/health",
    }
