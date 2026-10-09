from uuid import uuid4
from sqlalchemy import Boolean, ForeignKey, LargeBinary, String, Text, CheckConstraint, select, func, case
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def identifier():
    return str(uuid4())


class FenceCheckpoint(Base):
    __tablename__ = "privacy_fence_checkpoint"
    id: Mapped[int] = mapped_column(primary_key=True)
    authority_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int]
    digest: Mapped[str] = mapped_column(String(64))


class ConsentReceipt(Base):
    __tablename__ = "privacy_consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lifecycle_id: Mapped[str] = mapped_column(String(36), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(40))
    notice_hash: Mapped[str] = mapped_column(String(64))
    granted: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[int]
    expires_at: Mapped[int] = mapped_column(index=True)


class PrivacyPreference(Base):
    __tablename__ = "privacy_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    lifecycle_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(default=0)
    receipt_id: Mapped[str | None] = mapped_column(String(36))


class RecentAuthGrant(Base):
    __tablename__ = "privacy_grants"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    lifecycle_id: Mapped[str] = mapped_column(String(36))
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int]
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(36))
    expires_at: Mapped[int] = mapped_column(index=True)
    consumed_at: Mapped[int | None]


class PrivacyJob(Base):
    __tablename__ = "privacy_jobs"
    __table_args__ = (CheckConstraint("kind IN ('export', 'deletion')", name="privacy_job_kind"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[int] = mapped_column(index=True)
    lifecycle_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int]
    generation: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default="queued")
    phase: Mapped[str] = mapped_column(String(20), default="start")
    cursor: Mapped[int] = mapped_column(default=0)
    analysis_boundary: Mapped[int] = mapped_column(default=0)
    cursor_key: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[int]
    next_attempt_at: Mapped[int] = mapped_column(index=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    finished_at: Mapped[int | None]
    status_expires_at: Mapped[int | None] = mapped_column(index=True)
    staging_expires_at: Mapped[int | None]
    source_expires_at: Mapped[int | None]
    total_bytes: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(40))
    marker_id: Mapped[str | None] = mapped_column(String(36), index=True)
    receipt_digest: Mapped[str | None] = mapped_column(String(64), unique=True)


class ExportChunk(Base):
    __tablename__ = "privacy_export_chunks"
    job_id: Mapped[str] = mapped_column(ForeignKey("privacy_jobs.id", ondelete="CASCADE"), primary_key=True)
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary)


class DeletionMarker(Base):
    __tablename__ = "privacy_deletion_markers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[int] = mapped_column(index=True)
    lifecycle_id: Mapped[str] = mapped_column(String(36), index=True)
    scope: Mapped[str] = mapped_column(String(20))
    generation: Mapped[int]
    revision: Mapped[int]
    target_key: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[int]
    satisfied_at: Mapped[int | None]
    retry_count: Mapped[int] = mapped_column(default=0)
    exhausted: Mapped[bool] = mapped_column(Boolean, default=False)


class PrivacyOperation(Base):
    __tablename__ = "privacy_operations"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    lifecycle_id: Mapped[str] = mapped_column(String(36), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[int] = mapped_column(index=True)


class PrivacyRateBucket(Base):
    __tablename__ = "privacy_rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int]
    expires_at: Mapped[int] = mapped_column(index=True)


class AuditEvent(Base):
    __tablename__ = "privacy_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    lifecycle_id: Mapped[str] = mapped_column(String(36), index=True)
    event: Mapped[str] = mapped_column(String(40))
    reference: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[int]
    expires_at: Mapped[int] = mapped_column(index=True)


def fence_values(db, lifecycle_id):
    from .ownership import require_authority
    require_authority(db)
    return db.execute(select(
        func.max(case((DeletionMarker.scope == "account", 1), else_=0)),
        func.max(case((DeletionMarker.scope == "saved", DeletionMarker.generation), else_=None)),
        func.max(DeletionMarker.revision)).where(DeletionMarker.lifecycle_id == lifecycle_id)).one()
