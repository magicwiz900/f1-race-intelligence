from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API powering the F1 Race Intelligence prediction and telemetry analytics platform.",
    version="0.1.0",
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register central API Router under /api prefix
app.include_router(api_router, prefix="/api")


@app.get("/")
def read_root():
    """Root endpoint providing API info."""
    return {
        "title": app.title,
        "version": app.version,
        "docs_url": "/docs",
        "health_check": "/api/health",
    }
