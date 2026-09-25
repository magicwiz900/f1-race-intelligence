from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint to verify backend service readiness."""
    return HealthResponse(
        status="ok",
        service="f1-race-intelligence",
    )
