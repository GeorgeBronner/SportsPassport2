import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sports_passport.core.config import settings
from sports_passport.core.limiter import limiter
from sports_passport.db.database import engine, Base, SessionLocal
from sports_passport.db.seed import seed_leagues
from sports_passport.routers import auth, games, attendance, admin, teams, leagues, password_reset
from sports_passport.services.scheduler import start_scheduler, shutdown_scheduler
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Initialize Sentry as early as possible. Disabled (with a warning) when no DSN
# is configured so the app still runs locally / in environments without Sentry.
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=True,
    )
    logger.info("Sentry initialized (environment=%s)", settings.sentry_environment)
else:
    logger.warning("SENTRY_DSN not set — Sentry error reporting is disabled")

# Create database tables and seed static reference data
Base.metadata.create_all(bind=engine)
with SessionLocal() as _db:
    seed_leagues(_db)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the nightly sync scheduler on the running event loop, stop it on shutdown."""
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="API for tracking game attendance across CFB, MLB, NFL, NBA, and NHL",
    version="0.2.0",
    lifespan=lifespan,
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Rate limiting (forgot/reset-password endpoints)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS. Explicit origins, never "*": with allow_credentials the
# wildcard makes Starlette echo back whatever Origin asked, so any site could
# make credentialed calls to this API. The SPA is same-origin in production,
# so this list only needs to cover the Vite dev server (see CORS_ORIGINS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(password_reset.router)
app.include_router(leagues.router)
app.include_router(games.router)
app.include_router(teams.router)
app.include_router(attendance.router)
app.include_router(admin.router)


@app.get("/health")
def health_check():
    """Health check endpoint.

    Docker restarts the container on repeated failures, so this has to mean
    "can actually serve requests" — a process that's up but can't reach its
    database is not healthy.
    """
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        logger.error("Health check failed: database unreachable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        )
    return {"status": "healthy"}


# Team logos live under data/ (persistent volume in Docker; gitignored) because
# the frontend build wipes static/ on every run (vite emptyOutDir).
# check_dir=False lets the mount exist before fetch_team_logos.py first runs,
# so no restart is needed once the directory appears.
logos_dir = Path(__file__).parent.parent / "data" / "logos"
app.mount("/logos", StaticFiles(directory=str(logos_dir), check_dir=False), name="logos")

# Mount static files and serve SPA
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    # Mount static assets (JS, CSS, images)
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes"""
        # An unmatched /api path is a broken route, not a client-side one.
        # Serving the SPA shell there turns a 404 into a confusing 200 of HTML.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

        # If requesting a static file that exists, serve it
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Otherwise serve index.html for client-side routing
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        return {"message": "Frontend not built yet. Run: cd frontend && npm run build"}
