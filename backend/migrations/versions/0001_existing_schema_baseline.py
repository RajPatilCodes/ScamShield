"""Exact existing users/analyses baseline; no record transformation."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if set(sa.inspect(op.get_bind()).get_table_names()) - {"alembic_version"}:
        raise ValueError("Baseline creation requires an empty database")
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("analyses", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False), sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])


def downgrade():
    raise ValueError("Destructive baseline downgrade is intentionally unsupported")
