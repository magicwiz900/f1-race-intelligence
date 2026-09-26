from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

# Mount Static Frontend
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists() and (frontend_dir / "index.html").exists():
    app.mount("/dashboard", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.on_event("startup")
def preload_ml_models():
    """Preload trained ML models into singleton memory at application boot."""
    try:
        from app.services.prediction_service.model_loader import get_model_loader
        loader = get_model_loader()
        loader.load_models()
    except Exception as e:
        import logging
        logging.getLogger("app.main").warning("ML model preloading bypassed or failed: %s", e)


@app.get("/")
def read_root():
    """Root endpoint providing API info and frontend dashboard link."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "title": app.title,
        "version": app.version,
        "docs_url": "/docs",
        "health_check": "/api/health",
        "dashboard_url": "/dashboard",
    }


