from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAMAY_", env_file=ROOT / ".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = f"sqlite:///{(ROOT / 'samay.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    service_registry_path: Path | None = None
    research_registry_path: Path | None = ROOT / "research-registry.json"
    enable_research_forecasts: bool = True
    research_serving_registry_path: Path | None = ROOT / "research-serving-registry.json"
    historical_demo_date: date | None = None
    bundled_research_mode: bool = False
    marketplace_enabled: bool = True
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_from: str | None = None
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_sms_from: str | None = None
    twilio_whatsapp_from: str | None = None
    twilio_whatsapp_content_sid_en: str | None = None
    twilio_whatsapp_content_sid_kn: str | None = None
    public_app_url: str | None = None

    @model_validator(mode="after")
    def replay_mode(self):
        if self.database_url.startswith("sqlite:///") and not self.database_url.startswith("sqlite:////") and ":memory:" not in self.database_url:
            rel_part = self.database_url.replace("sqlite:///", "")
            if rel_part.startswith("./"):
                rel_part = rel_part[2:]
            path = Path(rel_part)
            if not path.is_absolute():
                self.database_url = f"sqlite:///{(ROOT / path).resolve().as_posix()}"
        if self.bundled_research_mode:
            if self.environment == 'production':
                raise ValueError('Bundled research mode is for local development/test only')
            self.historical_demo_date = None
        if self.historical_demo_date is not None and (self.environment == "production" or self.historical_demo_date >= date.today()):
            raise ValueError("Historical replay requires a past date and development/test environment")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
