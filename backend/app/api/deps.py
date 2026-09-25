import logging
from typing import Generator, Optional
from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to provide a SQLAlchemy database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """
    Reusable FastAPI dependency to enforce API-key protection via X-API-Key header.
    Key value is configured via environment variable API_KEY (settings.API_KEY).
    """
    required_key = settings.API_KEY
    if required_key:
        if not x_api_key or x_api_key != required_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key in X-API-Key header.",
            )
        return x_api_key
    
    # If no API_KEY configured in environment, allow with warning or require non-empty header
    if x_api_key:
        return x_api_key
    
    logger.debug("API_KEY setting is empty; request allowed without key.")
    return "unauthenticated"
