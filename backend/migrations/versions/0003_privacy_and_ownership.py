"""Privacy lifecycle and ownership. Original timestamps/passwords are preserved."""
import os
from datetime import datetime, timezone
from uuid import uuid4
from alembic import op, context
import sqlalchemy as sa
from app.privacy_config import policy, seconds
from app.privacy_models import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    orphan = bind.scalar(sa.text("SELECT COUNT(*) FROM analyses a LEFT JOIN users u ON u.id=a.user_id WHERE u.id IS NULL"))
    if orphan:
        raise ValueError("Orphan analyses require explicit resolution")
    rows = bind.execute(sa.text("SELECT id,user_id,created_at FROM analyses")).all()
    original_default = next(col for col in sa.inspect(bind).get_columns("analyses") if col["name"] == "created_at")["default"]
    sqlite_utc = bind.dialect.name == "sqlite" and "CURRENT_TIMESTAMP" in str(original_default).upper()
    resolution = context.config.attributes.get("legacy_timezone") or os.environ.get("PRIVACY_LEGACY_TIMEZONE")
    expiries = {}
    for row in rows:
        value = row.created_at
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("Legacy timestamp requires explicit resolution") from None
        if not isinstance(value, datetime):
            raise ValueError("Legacy timestamp requires explicit resolution")
        if value.tzinfo is None:
            if not sqlite_utc and resolution != "UTC":
                raise ValueError("Ambiguous legacy timezone requires explicit resolution")
            value = value.replace(tzinfo=timezone.utc)
        expiries[row.id] = int(value.timestamp()) + seconds(policy.analysis_days)
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("PRAGMA defer_foreign_keys=ON")
    op.add_column("users", sa.Column("lifecycle_id", sa.String(36)))
    op.add_column("users", sa.Column("data_generation", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("privacy_revision", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("privacy_state", sa.String(20), nullable=False, server_default="active"))
    identities = {}
    for user_id in bind.scalars(sa.text("SELECT id FROM users")):
        identities[user_id] = str(uuid4())
        bind.execute(sa.text("UPDATE users SET lifecycle_id=:life WHERE id=:id"), {"life": identities[user_id], "id": user_id})
    with op.batch_alter_table("users") as batch:
        batch.alter_column("lifecycle_id", existing_type=sa.String(36), nullable=False)
        batch.create_unique_constraint("uq_users_lifecycle_id", ["lifecycle_id"])
    for column in (sa.Column("record_key", sa.String(36)), sa.Column("lifecycle_id", sa.String(36)),
                   sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
                   sa.Column("expires_at", sa.Integer()), sa.Column("deleted_at", sa.Integer()),
                   sa.Column("provenance", sa.String(40), nullable=False, server_default="legacy_no_retroactive_consent"),
                   sa.Column("consent_id", sa.String(36))):
        op.add_column("analyses", column)
    for row in rows:
        bind.execute(sa.text("UPDATE analyses SET record_key=:key,lifecycle_id=:life,expires_at=:expiry WHERE id=:id"),
                     {"key": str(uuid4()), "life": identities[row.user_id], "expiry": expiries[row.id], "id": row.id})
    for table in Base.metadata.sorted_tables:
        if table.name.startswith("privacy_"):
            table.create(bind)
    with op.batch_alter_table("analyses") as batch:
        for name, kind in (("record_key", sa.String(36)), ("lifecycle_id", sa.String(36)), ("expires_at", sa.Integer())):
            batch.alter_column(name, existing_type=kind, nullable=False)
        batch.create_unique_constraint("uq_analyses_record_key", ["record_key"])
        batch.create_foreign_key("fk_analyses_user_id", "users", ["user_id"], ["id"])
        batch.create_foreign_key("fk_analyses_consent_id", "privacy_consents", ["consent_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_analyses_expires_at", ["expires_at"])
    if bind.dialect.name == "sqlite":
        # SQLite retains deferred DROP-parent counters even after the rebuilt
        # parent and all referenced rows are restored. Validate the complete
        # actual graph before clearing those stale counters; never disable FK
        # enforcement, leave violations, or commit an intermediate schema.
        if bind.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
            raise ValueError("Privacy migration foreign-key integrity check failed")
        bind.exec_driver_sql("PRAGMA defer_foreign_keys=OFF")


def downgrade():
    raise ValueError("Privacy downgrade requires a separately reviewed data-preserving procedure")
