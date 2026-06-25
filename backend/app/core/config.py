"""
Central settings module. Reads from .env (and real environment variables,
which always take precedence over .env for safety in deployed environments).

Add new operator credentials here as new operators are connected (e.g.
ANEX_LOGIN / ANEX_PASSWORD later).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    pegas_login: str = ""
    pegas_password: str = ""


settings = Settings()