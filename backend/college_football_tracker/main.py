import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from college_football_tracker.core.config import settings
from college_football_tracker.db.database import engine, Base
from college_football_tracker.routers import auth, games, attendance, admin, teams
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

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="API for tracking college football game attendance",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(games.router)
app.include_router(teams.router)
app.include_router(attendance.router)
app.include_router(admin.router)


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# Mount static files and serve SPA
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    # Mount static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes"""
        # If requesting a static file that exists, serve it
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Otherwise serve index.html for client-side routing
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        return {"message": "Frontend not built yet. Run: cd frontend && npm run build"}
