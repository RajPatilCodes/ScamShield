from sqlalchemy import ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CatalogBase(DeclarativeBase):
    pass


class CatalogPublication(CatalogBase):
    __tablename__ = "catalog_publications"

    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    jurisdiction: Mapped[str] = mapped_column(String(2), index=True)
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    published_at: Mapped[int]
    withdrawn_at: Mapped[int | None]


class CatalogCategory(CatalogBase):
    __tablename__ = "catalog_categories"
    __table_args__ = (
        PrimaryKeyConstraint("category_id", "publication_revision", "language"),
        ForeignKeyConstraint(["publication_revision"], ["catalog_publications.revision"]),
    )

    category_id: Mapped[str] = mapped_column(String(40))
    publication_revision: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer)


class CatalogGuideRevision(CatalogBase):
    __tablename__ = "catalog_guide_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("guide_id", "publication_revision", "language"),
        ForeignKeyConstraint(["publication_revision"], ["catalog_publications.revision"]),
    )

    guide_id: Mapped[str] = mapped_column(String(10))
    publication_revision: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(5))
    category_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(Text)
    warning_signs: Mapped[str] = mapped_column(Text)
    safe_actions: Mapped[str] = mapped_column(Text)
    recovery_guidance: Mapped[str] = mapped_column(Text)
    reporting_guidance: Mapped[str] = mapped_column(Text)
    prevention_tips: Mapped[str] = mapped_column(Text)
    false_positive_notes: Mapped[str] = mapped_column(Text)
    resource_ids: Mapped[str] = mapped_column(Text)
    lesson_ids: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text)
    reviewer_evidence: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(40))
    content_version: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[int | None]
    next_review_at: Mapped[int | None]


class EmergencyPlaybookRevision(CatalogBase):
    __tablename__ = "emergency_playbook_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("playbook_id", "publication_revision", "language"),
        ForeignKeyConstraint(["publication_revision"], ["catalog_publications.revision"]),
    )

    playbook_id: Mapped[str] = mapped_column(String(40))
    publication_revision: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    immediate_actions: Mapped[str] = mapped_column(Text)
    preserve_evidence: Mapped[str] = mapped_column(Text)
    recovery_actions: Mapped[str] = mapped_column(Text)
    escalation_guidance: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text)
    content_version: Mapped[str] = mapped_column(String(40))
    review_status: Mapped[str] = mapped_column(String(40))
    next_review_at: Mapped[int | None]


class LessonRevision(CatalogBase):
    __tablename__ = "lesson_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("lesson_id", "publication_revision", "language"),
        ForeignKeyConstraint(["publication_revision"], ["catalog_publications.revision"]),
    )

    lesson_id: Mapped[str] = mapped_column(String(40))
    publication_revision: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    sections: Mapped[str] = mapped_column(Text)
    knowledge_checks: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text)
    content_version: Mapped[str] = mapped_column(String(40))
    review_status: Mapped[str] = mapped_column(String(40))
    next_review_at: Mapped[int | None]


class ChecklistRevision(CatalogBase):
    __tablename__ = "checklist_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("checklist_id", "publication_revision", "language"),
        ForeignKeyConstraint(["publication_revision"], ["catalog_publications.revision"]),
    )

    checklist_id: Mapped[str] = mapped_column(String(40))
    publication_revision: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    items: Mapped[str] = mapped_column(Text)
    content_version: Mapped[str] = mapped_column(String(40))
    review_status: Mapped[str] = mapped_column(String(40))
    next_review_at: Mapped[int | None]


class TrustedResourceRevision(CatalogBase):
    __tablename__ = "trusted_resource_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("resource_id", "publication_revision", "language"),
        ForeignKeyConstraint(["publication_revision"], ["catalog_publications.revision"]),
    )

    resource_id: Mapped[str] = mapped_column(String(60))
    publication_revision: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(5))
    name: Mapped[str] = mapped_column(String(200))
    jurisdiction: Mapped[str] = mapped_column(String(2))
    destination: Mapped[str | None] = mapped_column(String(500))
    publisher: Mapped[str] = mapped_column(String(200))
    source_references: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(20))
    verification_date: Mapped[int | None]
    next_review_at: Mapped[int | None]
    content_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    withdrawn: Mapped[bool] = mapped_column(default=False, server_default="0")
