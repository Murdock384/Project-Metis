from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./metis.db"
    dev_user_id: int = 1
    dev_user_name: str = "Dev User"

    # Seed values for a user's first UserPreference row; the solver reads the
    # per-user record, not these.
    work_start_hour: int = 8
    work_end_hour: int = 22
    horizon_days: int = 7
    slot_minutes: int = 15
    peak_focus_start_hour: int = 9
    peak_focus_end_hour: int = 12
    min_break_minutes: int = 0
    max_daily_task_minutes: int = 8 * 60

    cors_origins: list[str] = ["*"]

    # Routes API credentials stay on the backend.  The mobile/web client only
    # calls our transport endpoints and never receives this key.
    google_maps_api_key: str | None = None
    google_routes_base_url: str = "https://routes.googleapis.com/directions/v2:computeRoutes"
    google_routes_timeout_seconds: float = 10.0
    user_timezone: str = "Europe/Warsaw"

    class Config:
        env_file = ".env"


settings = Settings()
