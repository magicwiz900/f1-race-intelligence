from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.races import router as races_router
from app.api.drivers import router as drivers_router
from app.api.teams import router as teams_router
from app.api.sessions import router as sessions_router
from app.api.predictions import router as predictions_router
from app.api.protected import router as protected_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(races_router)
api_router.include_router(drivers_router)
api_router.include_router(teams_router)
api_router.include_router(sessions_router)
api_router.include_router(predictions_router)
api_router.include_router(protected_router)

__all__ = ["api_router"]
