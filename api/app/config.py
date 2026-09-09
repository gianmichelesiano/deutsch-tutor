from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://deutsch:deutsch@localhost:5433/deutsch_tutor"
    api_prefix: str = "/api"


settings = Settings()
