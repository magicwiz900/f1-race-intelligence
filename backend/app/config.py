from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "F1 Race Intelligence API"
    APP_ENV: str = "development"
    
    # Database configuration placeholder
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/f1_race_intelligence"
    
    # API key placeholder
    API_KEY: str = ""
    
    # CORS Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
