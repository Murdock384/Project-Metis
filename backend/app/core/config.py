from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./metis.db"
    dev_user_id: int = 1
    dev_user_name: str = "Dev User"

    # Scheduler defaults (Phase 0: hardcoded, replaced by UserPreference later)
    work_start_hour: int = 8
    work_end_hour: int = 22
    horizon_days: int = 7
    slot_minutes: int = 15

    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
