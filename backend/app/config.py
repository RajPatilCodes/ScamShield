from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "sqlite:///./scamshield.db"
    jwt_secret: str
    jwt_issuer: str = "scamshield"
    jwt_audience: str = "scamshield-mobile"
    public_api_url: str = "http://10.0.2.2:8000"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    # Costs and verification expiry are explicit operator inputs, not invented policy defaults.
    argon2_time_cost: int = Field(gt=0)
    argon2_memory_cost: int = Field(ge=8)
    argon2_parallelism: int = Field(gt=0)
    verification_expire_minutes: int = Field(gt=0)
    email_adapter: str = "capture"
    smtp_host: str | None = None
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_timeout_seconds: float | None = Field(default=None, gt=0)
    email_sender: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return value.replace("postgres://", "postgresql+psycopg://", 1)

    @model_validator(mode="after")
    def validate_security(self):
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Invalid environment")
        try:
            url = make_url(self.database_url)
        except ArgumentError:
            raise ValueError("Invalid database URL") from None
        if url.drivername not in {"sqlite", "postgresql+psycopg"} or not url.database:
            raise ValueError("Use a configured SQLite or PostgreSQL database")
        if self.argon2_memory_cost < 8 * self.argon2_parallelism:
            raise ValueError("Argon2 memory must support configured parallelism")
        if not self.jwt_secret or not self.jwt_issuer or not self.jwt_audience:
            raise ValueError("Authentication configuration is required")
        api_url = urlsplit(self.public_api_url)
        if not api_url.hostname or api_url.username or api_url.password or api_url.scheme not in {"https", "http"}:
            raise ValueError("Invalid public API URL")
        if self.email_adapter not in {"capture", "smtp"}:
            raise ValueError("Invalid email adapter")
        if self.environment == "production":
            secret = self.jwt_secret.lower()
            if len(self.jwt_secret.encode()) < 32 or len(set(secret)) == 1 or any(word in secret for word in
                    ("change-me", "changeme", "placeholder", "example", "test-secret", "development", "password", "your-secret", "replace-me", "default-secret")):
                raise ValueError("Unsafe production signing secret")
            if api_url.scheme != "https" or any(not origin.startswith("https://") for origin in self.cors_origin_list):
                raise ValueError("Production credential flows require HTTPS")
            if url.drivername != "postgresql+psycopg" or not url.host or not url.username or not url.password:
                raise ValueError("Production requires explicitly configured PostgreSQL")
            if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Production database transport must require TLS")
            if self.email_adapter != "smtp":
                raise ValueError("Production delivery must be explicitly configured")
        if self.email_adapter == "smtp" and not all((self.smtp_host, self.smtp_username, self.smtp_password, self.email_sender, self.smtp_timeout_seconds)):
            raise ValueError("SMTP delivery configuration is incomplete")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
