"""Validated, operator-controlled import for public Phase 4 content.

The API has no content mutation route. A manifest is validated in full before
one immutable publication revision is inserted into the catalog tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog_config import (
    DEFAULT_JURISDICTION,
    DRAFT_STATUS,
    GUIDE_REVIEWED,
    GUIDE_REVIEW_PENDING,
    REQUIRED_GUIDE_IDS,
    RESOURCE_UNVERIFIED,
    RESOURCE_VERIFIED,
    RESOURCE_WITHDRAWN,
    SUPPORTED_JURISDICTIONS,
    SUPPORTED_LANGUAGES,
    PUBLISHED_STATUS,
    WITHDRAWN_STATUS,
)
from .catalog_models import (
    CatalogCategory,
    CatalogGuideRevision,
    CatalogPublication,
    ChecklistRevision,
    EmergencyPlaybookRevision,
    LessonRevision,
    TrustedResourceRevision,
)


class ContentError(ValueError):
    pass


class StrictContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _https_sources(value: list[str]) -> list[str]:
    for source in value:
        parsed = urlsplit(source)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("content sources must be HTTPS URLs without credentials")
    return value


class Manifest(StrictContentModel):
    schema_version: int = Field(ge=1)
    revision: int = Field(gt=0)
    jurisdiction: str
    languages: list[str]
    publication_status: str = PUBLISHED_STATUS
    files: dict[str, str | list[str]]
    content_digest: str | None = None


class CategoryContent(StrictContentModel):
    id: str = Field(min_length=1, max_length=40)
    language: str
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1)
    sort_order: int = Field(ge=0)


class GuideContent(StrictContentModel):
    id: str = Field(min_length=1, max_length=10)
    language: str
    category_id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    warning_signs: list[str] = Field(min_length=1)
    safe_actions: list[str] = Field(min_length=1)
    recovery_guidance: list[str] = Field(min_length=1)
    reporting_guidance: list[str] = Field(min_length=1)
    prevention_tips: list[str] = Field(min_length=1)
    false_positive_notes: list[str] = Field(min_length=1)
    resource_ids: list[str]
    lesson_ids: list[str]
    sources: list[str]
    reviewer_evidence: list[str]
    review_status: str
    content_version: str = Field(min_length=1, max_length=40)
    reviewed_at: int | None = None
    next_review_at: int | None = None

    @field_validator("sources")
    @classmethod
    def valid_sources(cls, value: list[str]) -> list[str]:
        return _https_sources(value)


class PlaybookContent(StrictContentModel):
    id: str = Field(min_length=1, max_length=40)
    language: str
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    immediate_actions: list[str] = Field(min_length=1)
    preserve_evidence: list[str] = Field(min_length=1)
    recovery_actions: list[str] = Field(min_length=1)
    escalation_guidance: list[str] = Field(min_length=1)
    sources: list[str]
    content_version: str = Field(min_length=1, max_length=40)
    review_status: str
    next_review_at: int | None = None

    @field_validator("sources")
    @classmethod
    def valid_sources(cls, value: list[str]) -> list[str]:
        return _https_sources(value)


class KnowledgeCheckContent(StrictContentModel):
    id: str = Field(min_length=1, max_length=40)
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_option: int = Field(ge=0)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_answer(self):
        if self.correct_option >= len(self.options):
            raise ValueError("Knowledge-check answer must reference an option")
        return self


class LessonContent(StrictContentModel):
    id: str = Field(min_length=1, max_length=40)
    language: str
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    sections: list[dict[str, Any]] = Field(min_length=1)
    knowledge_checks: list[KnowledgeCheckContent] = Field(min_length=1, max_length=10)
    sources: list[str]
    content_version: str = Field(min_length=1, max_length=40)
    review_status: str
    next_review_at: int | None = None

    @field_validator("sources")
    @classmethod
    def valid_sources(cls, value: list[str]) -> list[str]:
        return _https_sources(value)


class ChecklistItem(StrictContentModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1)


class ChecklistContent(StrictContentModel):
    id: str = Field(min_length=1, max_length=40)
    language: str
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    items: list[ChecklistItem] = Field(min_length=1, max_length=10)
    content_version: str = Field(min_length=1, max_length=40)
    review_status: str
    next_review_at: int | None = None


class ResourceContent(StrictContentModel):
    id: str = Field(min_length=1, max_length=60)
    language: str
    name: str = Field(min_length=1, max_length=200)
    jurisdiction: str
    destination: str | None = None
    publisher: str = Field(min_length=1, max_length=200)
    source_references: list[str]
    verification_status: str
    verification_date: int | None = None
    next_review_at: int | None = None
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    withdrawn: bool = False

    @field_validator("source_references")
    @classmethod
    def valid_source_references(cls, value: list[str]) -> list[str]:
        return _https_sources(value)

    @field_validator("destination")
    @classmethod
    def valid_destination(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("resource destinations must be HTTPS URLs without credentials")
        return value


def _resource_definition_payload(resource: ResourceContent) -> dict[str, Any]:
    return {
        "destination": resource.destination,
        "id": resource.id,
        "jurisdiction": resource.jurisdiction,
        "language": resource.language,
        "name": resource.name,
        "publisher": resource.publisher,
        "source_references": resource.source_references,
    }


def resource_definition_digest(resource: ResourceContent) -> str:
    encoded = json.dumps(
        _resource_definition_payload(resource),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ContentBundle:
    def __init__(
        self,
        manifest: Manifest,
        categories: list[CategoryContent],
        guides: list[GuideContent],
        playbooks: list[PlaybookContent],
        lessons: list[LessonContent],
        checklists: list[ChecklistContent],
        resources: list[ResourceContent],
    ):
        self.manifest = manifest
        self.categories = categories
        self.guides = guides
        self.playbooks = playbooks
        self.lessons = lessons
        self.checklists = checklists
        self.resources = resources

    def canonical_payload(self) -> dict[str, Any]:
        def dumped(values: Iterable[BaseModel]) -> list[dict[str, Any]]:
            return sorted((value.model_dump(mode="json") for value in values), key=lambda item: (item["id"], item["language"]))

        return {
            "schema_version": self.manifest.schema_version,
            "revision": self.manifest.revision,
            "jurisdiction": self.manifest.jurisdiction,
            "languages": sorted(self.manifest.languages),
            "publication_status": self.manifest.publication_status,
            "categories": dumped(self.categories),
            "guides": dumped(self.guides),
            "playbooks": dumped(self.playbooks),
            "lessons": dumped(self.lessons),
            "checklists": dumped(self.checklists),
            "resources": dumped(self.resources),
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.canonical_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContentError(f"Unable to read content file: {path.name}") from error


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ContentError("Content files must remain below the manifest directory")
    return candidate


def _records(root: Path, relative: str) -> list[dict[str, Any]]:
    value = _read_json(_safe_child(root, relative))
    if isinstance(value, dict):
        value = value.get("items")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ContentError(f"Content file must contain an array of objects: {relative}")
    return value


def _parse_items(model: type[BaseModel], root: Path, files: list[str]) -> list[Any]:
    values: list[Any] = []
    for relative in files:
        for item in _records(root, relative):
            try:
                values.append(model.model_validate(item))
            except ValidationError as error:
                raise ContentError(f"Invalid content in {relative}: {error}") from error
    return values


def _required_file(manifest: Manifest, name: str) -> str:
    value = manifest.files.get(name)
    if not isinstance(value, str) or not value:
        raise ContentError(f"Manifest is missing the {name} file")
    return value


def _validate_ids(values: Iterable[Any], label: str) -> set[tuple[str, str]]:
    identities = [(value.id, value.language) for value in values]
    if len(identities) != len(set(identities)):
        raise ContentError(f"Duplicate {label} language entry")
    return set(identities)


def validate_bundle(bundle: ContentBundle) -> ContentBundle:
    manifest = bundle.manifest
    if manifest.schema_version != 1:
        raise ContentError("Unsupported content manifest schema")
    if manifest.jurisdiction not in SUPPORTED_JURISDICTIONS:
        raise ContentError("Unsupported catalog jurisdiction")
    if not manifest.languages or "en" not in manifest.languages or any(language not in SUPPORTED_LANGUAGES for language in manifest.languages):
        raise ContentError("The manifest must include supported English content")
    if len(set(manifest.languages)) != len(manifest.languages):
        raise ContentError("Manifest languages must be unique")
    if manifest.publication_status not in {PUBLISHED_STATUS, DRAFT_STATUS, WITHDRAWN_STATUS}:
        raise ContentError("Invalid publication status")

    category_ids = _validate_ids(bundle.categories, "category")
    guide_ids = _validate_ids(bundle.guides, "guide")
    _validate_ids(bundle.playbooks, "playbook")
    lesson_ids = _validate_ids(bundle.lessons, "lesson")
    _validate_ids(bundle.checklists, "checklist")
    resource_ids = _validate_ids(bundle.resources, "resource")

    english_guides = {identifier for identifier, language in guide_ids if language == "en"}
    if english_guides != set(REQUIRED_GUIDE_IDS):
        missing = sorted(set(REQUIRED_GUIDE_IDS) - english_guides)
        extra = sorted(english_guides - set(REQUIRED_GUIDE_IDS))
        raise ContentError(f"Guide inventory mismatch; missing={missing}, extra={extra}")

    for guide in bundle.guides:
        if guide.language not in manifest.languages:
            raise ContentError(f"Guide {guide.id} uses an undeclared language")
        if (guide.category_id, guide.language) not in category_ids and (guide.category_id, "en") not in category_ids:
            raise ContentError(f"Guide {guide.id} references an unknown category")
        if guide.review_status not in {GUIDE_REVIEW_PENDING, GUIDE_REVIEWED}:
            raise ContentError(f"Guide {guide.id} has an invalid review status")
        if guide.review_status == GUIDE_REVIEWED and (not guide.reviewer_evidence or guide.reviewed_at is None):
            raise ContentError(f"Guide {guide.id} cannot claim review without evidence and a review date")
        if any(resource_id not in {identifier for identifier, _ in resource_ids} for resource_id in guide.resource_ids):
            raise ContentError(f"Guide {guide.id} references an unknown resource")
        if any(lesson_id not in {identifier for identifier, _ in lesson_ids} for lesson_id in guide.lesson_ids):
            raise ContentError(f"Guide {guide.id} references an unknown lesson")

    for item in [*bundle.playbooks, *bundle.lessons, *bundle.checklists]:
        if item.language not in manifest.languages:
            raise ContentError(f"Content item {item.id} uses an undeclared language")
        if item.review_status not in {GUIDE_REVIEW_PENDING, GUIDE_REVIEWED}:
            raise ContentError(f"Content item {item.id} has an invalid review status")

    resource_identity_ids = {identifier for identifier, _ in resource_ids}
    for resource in bundle.resources:
        if resource.jurisdiction != manifest.jurisdiction:
            raise ContentError(f"Resource {resource.id} has the wrong jurisdiction")
        if resource.verification_status not in {RESOURCE_UNVERIFIED, RESOURCE_VERIFIED, RESOURCE_WITHDRAWN}:
            raise ContentError(f"Resource {resource.id} has an invalid verification status")
        if resource.content_digest is not None and resource.content_digest != resource_definition_digest(resource):
            raise ContentError(f"Resource {resource.id} content digest does not match its canonical definition")
        if resource.verification_status == RESOURCE_VERIFIED and (
            not resource.source_references or not resource.destination or resource.verification_date is None
            or resource.content_digest is None
        ):
            raise ContentError(f"Resource {resource.id} cannot claim verification without evidence")
        if resource.verification_status == RESOURCE_WITHDRAWN and not resource.withdrawn:
            raise ContentError(f"Withdrawn resource {resource.id} must be marked withdrawn")
        if resource.id not in resource_identity_ids:
            raise ContentError(f"Invalid resource identity for {resource.id}")

    if manifest.publication_status == PUBLISHED_STATUS:
        if any(item.review_status != GUIDE_REVIEWED for item in [*bundle.guides, *bundle.playbooks, *bundle.lessons, *bundle.checklists]):
            raise ContentError("Published content requires editorial review")
        if any(item.verification_status == RESOURCE_UNVERIFIED for item in bundle.resources):
            raise ContentError("Published content cannot contain unverified resources")

    if manifest.content_digest is not None and manifest.content_digest != bundle.digest:
        raise ContentError("Manifest content digest does not match its content")
    return bundle


def load_manifest(path: str | Path) -> ContentBundle:
    manifest_path = Path(path).resolve()
    value = _read_json(manifest_path)
    try:
        manifest = Manifest.model_validate(value)
    except ValidationError as error:
        raise ContentError(f"Invalid manifest: {error}") from error
    root = manifest_path.parent
    categories = _parse_items(CategoryContent, root, [_required_file(manifest, "categories")])
    guide_files = manifest.files.get("guides", [])
    if not isinstance(guide_files, list) or not guide_files or not all(isinstance(item, str) for item in guide_files):
        raise ContentError("Manifest must list guide files")
    guides = _parse_items(GuideContent, root, guide_files)
    playbooks = _parse_items(PlaybookContent, root, [_required_file(manifest, "playbooks")])
    lessons = _parse_items(LessonContent, root, [_required_file(manifest, "lessons")])
    checklists = _parse_items(ChecklistContent, root, [_required_file(manifest, "checklists")])
    resources = _parse_items(ResourceContent, root, [_required_file(manifest, "resources")])
    return validate_bundle(ContentBundle(manifest, categories, guides, playbooks, lessons, checklists, resources))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def publish_bundle(db: Session, bundle: ContentBundle, *, now: int | None = None) -> str:
    validate_bundle(bundle)
    if bundle.manifest.publication_status not in {PUBLISHED_STATUS, DRAFT_STATUS}:
        raise ContentError("Withdrawn manifests cannot be imported into the public catalog")
    timestamp = int(time.time()) if now is None else now
    existing = db.get(CatalogPublication, bundle.manifest.revision)
    if existing is not None:
        if existing.digest == bundle.digest:
            return bundle.digest
        raise ContentError("Publication revision already exists with a different digest")

    current = db.scalars(select(CatalogPublication).where(
        CatalogPublication.jurisdiction == bundle.manifest.jurisdiction,
        CatalogPublication.status.in_((PUBLISHED_STATUS, DRAFT_STATUS)),
    )).all()
    for publication in current:
        if bundle.manifest.publication_status == PUBLISHED_STATUS or publication.status == DRAFT_STATUS:
            publication.status = WITHDRAWN_STATUS
            publication.withdrawn_at = timestamp

    db.add(CatalogPublication(
        revision=bundle.manifest.revision,
        jurisdiction=bundle.manifest.jurisdiction,
        digest=bundle.digest,
        status=bundle.manifest.publication_status,
        published_at=timestamp,
        withdrawn_at=None,
    ))
    db.flush()
    for item in bundle.categories:
        db.add(CatalogCategory(
            category_id=item.id, publication_revision=bundle.manifest.revision, language=item.language,
            title=item.title, summary=item.summary, sort_order=item.sort_order,
        ))
    for item in bundle.guides:
        db.add(CatalogGuideRevision(
            guide_id=item.id, publication_revision=bundle.manifest.revision, language=item.language,
            category_id=item.category_id, title=item.title, summary=item.summary, scenario=item.scenario,
            warning_signs=_json(item.warning_signs), safe_actions=_json(item.safe_actions),
            recovery_guidance=_json(item.recovery_guidance), reporting_guidance=_json(item.reporting_guidance),
            prevention_tips=_json(item.prevention_tips), false_positive_notes=_json(item.false_positive_notes),
            resource_ids=_json(item.resource_ids), lesson_ids=_json(item.lesson_ids), sources=_json(item.sources),
            reviewer_evidence=_json(item.reviewer_evidence), review_status=item.review_status,
            content_version=item.content_version, reviewed_at=item.reviewed_at, next_review_at=item.next_review_at,
        ))
    for item in bundle.playbooks:
        db.add(EmergencyPlaybookRevision(
            playbook_id=item.id, publication_revision=bundle.manifest.revision, language=item.language,
            title=item.title, summary=item.summary, immediate_actions=_json(item.immediate_actions),
            preserve_evidence=_json(item.preserve_evidence), recovery_actions=_json(item.recovery_actions),
            escalation_guidance=_json(item.escalation_guidance), sources=_json(item.sources),
            content_version=item.content_version, review_status=item.review_status, next_review_at=item.next_review_at,
        ))
    for item in bundle.lessons:
        db.add(LessonRevision(
            lesson_id=item.id, publication_revision=bundle.manifest.revision, language=item.language,
            title=item.title, summary=item.summary, sections=_json(item.sections),
            knowledge_checks=_json([check.model_dump(mode="json") for check in item.knowledge_checks]),
            sources=_json(item.sources), content_version=item.content_version,
            review_status=item.review_status, next_review_at=item.next_review_at,
        ))
    for item in bundle.checklists:
        db.add(ChecklistRevision(
            checklist_id=item.id, publication_revision=bundle.manifest.revision, language=item.language,
            title=item.title, summary=item.summary, items=_json([item.model_dump(mode="json") for item in item.items]),
            content_version=item.content_version, review_status=item.review_status, next_review_at=item.next_review_at,
        ))
    for item in bundle.resources:
        db.add(TrustedResourceRevision(
            resource_id=item.id, publication_revision=bundle.manifest.revision, language=item.language,
            name=item.name, jurisdiction=item.jurisdiction, destination=item.destination, publisher=item.publisher,
            source_references=_json(item.source_references), verification_status=item.verification_status,
            verification_date=item.verification_date, next_review_at=item.next_review_at,
            content_digest=item.content_digest, withdrawn=item.withdrawn,
        ))
    db.commit()
    return bundle.digest


def _main() -> None:
    parser = argparse.ArgumentParser(description="Validate or publish a ScamShield public content manifest")
    parser.add_argument("action", choices=("validate", "publish"))
    parser.add_argument("manifest")
    args = parser.parse_args()
    bundle = load_manifest(args.manifest)
    if args.action == "validate":
        print(json.dumps({"revision": bundle.manifest.revision, "digest": bundle.digest, "guides": len(bundle.guides)}))
        return
    from .database import SessionLocal

    with SessionLocal() as db:
        print(json.dumps({"revision": bundle.manifest.revision, "digest": publish_bundle(db, bundle), "guides": len(bundle.guides)}))


if __name__ == "__main__":
    _main()
