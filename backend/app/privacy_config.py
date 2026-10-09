"""Approved implementation inputs; no legal or external-backup policy."""
import hashlib
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PrivacySettings(BaseSettings):
    # Independent, operator-designated authority; never created on API startup.
    authority_path: str | None = None
    analysis_days: int = Field(default=90, gt=0)
    export_hours: int = Field(default=24, gt=0)
    artifact_hours: int = Field(default=24, gt=0)
    consent_days: int = Field(default=730, gt=0)
    audit_days: int = Field(default=365, gt=0)
    status_days: int = Field(default=30, gt=0)
    marker_min_days: int = Field(default=30, gt=0)
    recent_auth_seconds: int = Field(default=300, gt=0)
    rate_window_seconds: int = Field(default=900, gt=0)
    reauth_limit: int = Field(default=5, gt=0)
    export_create_limit: int = Field(default=3, gt=0)
    export_read_limit: int = Field(default=10, gt=0)
    deletion_limit: int = Field(default=3, gt=0)
    receipt_limit: int = Field(default=10, gt=0)
    retry_initial_seconds: int = Field(default=60, gt=0)
    retry_max_seconds: int = Field(default=3600, gt=0)
    automatic_retries: int = Field(default=5, ge=0)
    poll_seconds: int = Field(default=300, gt=0)
    batch_size: int = Field(default=100, gt=0)
    export_max_bytes: int = Field(default=100_000_000, gt=0)
    account_export_jobs: int = Field(default=1, gt=0)
    global_export_jobs: int = Field(default=2, gt=0)
    maintenance_hour_utc: int = Field(default=2, ge=0, le=23)
    maintenance_minute_utc: int = Field(default=0, ge=0, le=59)
    model_config = SettingsConfigDict(env_prefix="PRIVACY_", extra="ignore", hide_input_in_errors=True)


policy = PrivacySettings()
PURPOSE = "saved_analysis_storage"
NOTICE_VERSION = "product-1"
NOTICE = ("Product data control, not a legal notice: saving is optional. "
          f"Explicitly saved text checks are kept for {policy.analysis_days} days unless deleted earlier. "
          "Turning saving off stops future saves. Existing saved checks can be deleted separately.")
NOTICE_HASH = hashlib.sha256(NOTICE.encode()).hexdigest()


def seconds(days: int) -> int:
    return days * 24 * 60 * 60
