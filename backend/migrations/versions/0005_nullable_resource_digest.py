"""Allow draft resources without a content digest."""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("trusted_resource_revisions") as batch:
        batch.alter_column("content_digest", existing_type=sa.String(64), nullable=True)


def downgrade():
    raise ValueError("Resource digest nullability downgrade requires a separately reviewed data-preserving procedure")
