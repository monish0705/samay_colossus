from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAMAY_", env_file=ROOT / ".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = f"sqlite:///{(ROOT / 'samay.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    service_registry_path: Path | None = None
    research_registry_path: Path | None = None
    enable_research_forecasts: bool = False
    research_serving_registry_path: Path | None = None
    historical_demo_date: date | None = None

    @model_validator(mode="after")
    def replay_mode(self):
        if self.historical_demo_date is not None and (self.environment == "production" or self.historical_demo_date >= date.today()):
            raise ValueError("Historical replay requires a past date and development/test environment")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
