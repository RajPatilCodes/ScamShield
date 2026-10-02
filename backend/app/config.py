from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./scamshield.db"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return value.replace("postgres://", "postgresql+psycopg://", 1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
