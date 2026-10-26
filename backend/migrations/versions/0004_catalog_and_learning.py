"""Additive public catalog, emergency, learning and resource revisions."""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "catalog_publications",
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("jurisdiction", sa.String(2), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("published_at", sa.Integer(), nullable=False),
        sa.Column("withdrawn_at", sa.Integer()),
    )
    op.create_index("ix_catalog_publications_jurisdiction", "catalog_publications", ["jurisdiction"])
    op.create_index("ix_catalog_publications_status", "catalog_publications", ["status"])

    def versioned_table(name, id_name, id_type, columns):
        op.create_table(
            name,
            sa.Column(id_name, id_type, nullable=False),
            sa.Column("publication_revision", sa.Integer(), nullable=False),
            sa.Column("language", sa.String(5), nullable=False),
            *columns,
            sa.PrimaryKeyConstraint(id_name, "publication_revision", "language"),
            sa.ForeignKeyConstraint(["publication_revision"], ["catalog_publications.revision"]),
        )

    versioned_table("catalog_categories", "category_id", sa.String(40), [
        sa.Column("title", sa.String(160), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    ])
    versioned_table("catalog_guide_revisions", "guide_id", sa.String(10), [
        sa.Column("category_id", sa.String(40), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("warning_signs", sa.Text(), nullable=False), sa.Column("safe_actions", sa.Text(), nullable=False),
        sa.Column("recovery_guidance", sa.Text(), nullable=False), sa.Column("reporting_guidance", sa.Text(), nullable=False),
        sa.Column("prevention_tips", sa.Text(), nullable=False), sa.Column("false_positive_notes", sa.Text(), nullable=False),
        sa.Column("resource_ids", sa.Text(), nullable=False), sa.Column("lesson_ids", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=False), sa.Column("reviewer_evidence", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False), sa.Column("content_version", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.Integer()), sa.Column("next_review_at", sa.Integer()),
    ])
    versioned_table("emergency_playbook_revisions", "playbook_id", sa.String(40), [
        sa.Column("title", sa.String(200), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("immediate_actions", sa.Text(), nullable=False), sa.Column("preserve_evidence", sa.Text(), nullable=False),
        sa.Column("recovery_actions", sa.Text(), nullable=False), sa.Column("escalation_guidance", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=False), sa.Column("content_version", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False), sa.Column("next_review_at", sa.Integer()),
    ])
    versioned_table("lesson_revisions", "lesson_id", sa.String(40), [
        sa.Column("title", sa.String(200), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sections", sa.Text(), nullable=False), sa.Column("knowledge_checks", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=False), sa.Column("content_version", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False), sa.Column("next_review_at", sa.Integer()),
    ])
    versioned_table("checklist_revisions", "checklist_id", sa.String(40), [
        sa.Column("title", sa.String(200), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("items", sa.Text(), nullable=False), sa.Column("content_version", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False), sa.Column("next_review_at", sa.Integer()),
    ])
    versioned_table("trusted_resource_revisions", "resource_id", sa.String(60), [
        sa.Column("name", sa.String(200), nullable=False), sa.Column("jurisdiction", sa.String(2), nullable=False),
        sa.Column("destination", sa.String(500)), sa.Column("publisher", sa.String(200), nullable=False),
        sa.Column("source_references", sa.Text(), nullable=False), sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("verification_date", sa.Integer()), sa.Column("next_review_at", sa.Integer()),
        sa.Column("content_digest", sa.String(64), nullable=False), sa.Column("withdrawn", sa.Boolean(), nullable=False, server_default=sa.false()),
    ])


def downgrade():
    raise ValueError("Catalog downgrade requires a separately reviewed data-preserving procedure")
