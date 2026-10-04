"""Authentication tables and account state; preserves original records/hashes."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("auth_sessions", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False), sa.Column("idle_expires_at", sa.Integer(), nullable=False),
        sa.Column("absolute_expires_at", sa.Integer(), nullable=False), sa.Column("revoked_at", sa.Integer()),
        sa.CheckConstraint("idle_expires_at <= absolute_expires_at", name="session_expiry_order"))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table("refresh_credentials", sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("auth_sessions.id"), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False), sa.Column("consumed_at", sa.Integer()))
    op.create_index("ix_refresh_credentials_session_id", "refresh_credentials", ["session_id"])
    op.create_table("auth_challenges", sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False), sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.Integer()),
        sa.CheckConstraint("purpose IN ('verification', 'recovery')", name="challenge_purpose"))
    op.create_index("ix_auth_challenges_user_id", "auth_challenges", ["user_id"])
    op.create_table("auth_rate_buckets", sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("expires_at", sa.Integer(), nullable=False))


def downgrade():
    raise ValueError("Authentication downgrade requires a separately reviewed data-preserving procedure")
