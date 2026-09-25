from fastapi import APIRouter, Depends
from app.api.deps import verify_api_key

router = APIRouter(tags=["Security Demo"])


@router.get(
    "/protected-demo",
    summary="Protected API Key Demo Endpoint",
    description="Demonstrates API-key protection using the X-API-Key header dependency. Requires a valid API key when API_KEY is set in environment settings.",
)
def protected_demo_endpoint(api_key: str = Depends(verify_api_key)):
    return {
        "status": "authenticated",
        "message": "Access granted to protected endpoint.",
        "api_key_status": "valid" if api_key != "unauthenticated" else "unconfigured_environment",
    }
