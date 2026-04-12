from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_PATH = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/juriq"

    llm_provider: Literal["gemini", "groq", "local"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_api_key: str = "local"


settings = Settings()
