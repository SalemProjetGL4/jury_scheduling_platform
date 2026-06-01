from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_PATH = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore")

    translator_service_url: str = "http://localhost:8012"
    solver_service_url: str = "http://localhost:8010"
    reflector_service_url: str = "http://localhost:8013"
    updater_service_url: str = "http://localhost:8014"

    gateway_timeout_seconds: int = 30
    solver_timeout_seconds: int = 600
    updater_timeout_seconds: int = 120


settings = Settings()
