from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    lifecycle_id: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid4()))
    data_generation: Mapped[int] = mapped_column(default=0, server_default="0")
    privacy_revision: Mapped[int] = mapped_column(default=0, server_default="0")
    privacy_state: Mapped[str] = mapped_column(String(20), default="active", server_default="active")


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    score: Mapped[int]
    verdict: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    record_key: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid4()))
    lifecycle_id: Mapped[str] = mapped_column(String(36))
    generation: Mapped[int] = mapped_column(default=0, server_default="0")
    expires_at: Mapped[int] = mapped_column(index=True)
    deleted_at: Mapped[int | None]
    provenance: Mapped[str] = mapped_column(String(40), default="current_consent", server_default="legacy_no_retroactive_consent")
    consent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("privacy_consents.id", ondelete="SET NULL"))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (CheckConstraint("idle_expires_at <= absolute_expires_at", name="session_expiry_order"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[int]
    idle_expires_at: Mapped[int]
    absolute_expires_at: Mapped[int]
    revoked_at: Mapped[int | None]


class RefreshCredential(Base):
    __tablename__ = "refresh_credentials"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id"), index=True)
    expires_at: Mapped[int]
    consumed_at: Mapped[int | None]


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    __table_args__ = (CheckConstraint("purpose IN ('verification', 'recovery')", name="challenge_purpose"),)
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[int]
    consumed_at: Mapped[int | None]


class AuthRateBucket(Base):
    __tablename__ = "auth_rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int]
    expires_at: Mapped[int]


# Register the additive privacy tables for both Alembic and application metadata.
from . import privacy_models  # noqa: E402,F401


# Validate the independent authority before existing authentication can load
# account rows. Missing/stale fencing blocks activation, including old restores.
from sqlalchemy import event, select  # noqa: E402


@event.listens_for(User, "load")
def restored_lifecycle_fence(user, context):
    account, generation, revision = privacy_models.fence_values(context.session, user.lifecycle_id)
    if revision is not None:
        user.privacy_revision = max(user.privacy_revision, revision)
    if account:
        user.is_active = False
        user.privacy_state = "deleting"
    if generation is not None:
        user.data_generation = max(user.data_generation, generation + 1)
