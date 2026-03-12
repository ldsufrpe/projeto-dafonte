from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://fontegest:fontegest@db:5432/fontegest"

    # ERP
    ERP_MODE: str = "mock"  # "mock" | "datasnap"
    ERP_BASE_URL: str = ""
    ERP_USER: str = ""
    ERP_PASSWORD: str = ""
    ERP_TIMEOUT: int = 30
    SYNC_CRON: str = "0 */2 7-21 * *"  # every 2h from 07:00-21:00


settings = Settings()
