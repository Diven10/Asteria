from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "ASTERIA Backend"
    app_version: str = "0.1.0"
    environment: str = "development"
    asteria_model_path: str = "app/ml/models/baseline.joblib"
    database_url: str = "postgresql+psycopg://asteria:asteria@localhost:5432/asteria"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
