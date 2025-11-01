from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from college_football_tracker.core.config import settings
from college_football_tracker.db.database import engine, Base
from college_football_tracker.routers import auth, games, attendance, admin, teams

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


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "College Football Game Tracker API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
