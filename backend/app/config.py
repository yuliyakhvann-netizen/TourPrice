from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://tourprice:tourprice@db:5432/tourprice"

    # Sync URL used by Alembic (no asyncpg driver)
    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "")

    funsun_login: str = ""
    funsun_password: str = ""
    funsun_base_url: str = "https://b2b.funsun.kz"

    pegas_login: str = ""
    pegas_password: str = ""
    pegas_base_url: str = "https://b2b.pegast.kz"

    anex_login: str = ""
    anex_password: str = ""
    anex_base_url: str = "https://b2b.anextour.com"

    kompas_login: str = ""
    kompas_password: str = ""
    kompas_base_url: str = "https://b2b.kompastour.kz"

    scrape_interval_hours: int = 2


settings = Settings()
