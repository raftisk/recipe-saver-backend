from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./recipe_saver.db"
    session_ttl_days: int = 30
    session_sliding_window_days: int = 7
    cors_origins: list[str] = ["*"]
    max_html_bytes: int = 2 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
