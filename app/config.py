import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_version: str
    base_url: str
    log_level: str


def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./shortlink.db"),
        app_version=os.environ.get("APP_VERSION", "dev"),
        base_url=os.environ.get("BASE_URL", "http://localhost:8000"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
