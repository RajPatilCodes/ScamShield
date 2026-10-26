from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Language = Literal["en", "hi"]


class PublicLanguageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_language: Language
    content_language: Language
    fallback_used: bool


class CategoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    summary: str
    sort_order: int
    language: PublicLanguageMetadata


class GuideResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category_id: str
    title: str
    summary: str
    scenario: str
    warning_signs: list[str]
    safe_actions: list[str]
    recovery_guidance: list[str]
    reporting_guidance: list[str]
    prevention_tips: list[str]
    false_positive_notes: list[str]
    resource_ids: list[str]
    lesson_ids: list[str]
    review_status: str
    content_version: str
    language: PublicLanguageMetadata


class KnowledgeCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    options: list[str]
    correct_option: int
    explanation: str


class LessonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    summary: str
    sections: list[dict[str, object]]
    knowledge_checks: list[KnowledgeCheckResponse]
    review_status: str
    content_version: str
    language: PublicLanguageMetadata


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str


class ChecklistResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    summary: str
    items: list[ChecklistItemResponse]
    review_status: str
    content_version: str
    language: PublicLanguageMetadata


class EmergencyPlaybookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    summary: str
    immediate_actions: list[str]
    preserve_evidence: list[str]
    recovery_actions: list[str]
    escalation_guidance: list[str]
    review_status: str
    content_version: str
    language: PublicLanguageMetadata


class ResourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    jurisdiction: str
    destination: str | None
    publisher: str
    source_references: list[str]
    verification_status: str
    verification_date: int | None
    next_review_at: int | None
    content_digest: str | None
    withdrawn: bool
    language: PublicLanguageMetadata


class CursorPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_cursor: str | None = Field(default=None, max_length=256)


class CategoryPage(CursorPage):
    items: list[CategoryResponse]


class GuidePage(CursorPage):
    items: list[GuideResponse]


class LessonPage(CursorPage):
    items: list[LessonResponse]


class ChecklistPage(CursorPage):
    items: list[ChecklistResponse]


class EmergencyPage(CursorPage):
    items: list[EmergencyPlaybookResponse]


class ResourcePage(CursorPage):
    items: list[ResourceResponse]


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GuideResponse]
    next_cursor: str | None = Field(default=None, max_length=256)
