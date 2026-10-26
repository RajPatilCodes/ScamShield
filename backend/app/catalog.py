from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable, Iterable
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from .catalog_config import (
    DEFAULT_JURISDICTION,
    DEFAULT_LANGUAGE,
    DRAFT_STATUS,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
    PUBLISHED_STATUS,
)
from .catalog_models import CatalogCategory, CatalogGuideRevision, CatalogPublication, ChecklistRevision, EmergencyPlaybookRevision, LessonRevision, TrustedResourceRevision


def _publication(db: Session, jurisdiction: str) -> CatalogPublication:
    result = db.scalar(select(CatalogPublication).where(
        CatalogPublication.jurisdiction == jurisdiction,
        CatalogPublication.status.in_((PUBLISHED_STATUS, DRAFT_STATUS)),
    ).order_by(
        case((CatalogPublication.status == PUBLISHED_STATUS, 0), else_=1),
        CatalogPublication.revision.desc(),
    ))
    if result is None:
        raise HTTPException(503, "Public catalog unavailable")
    return result


def _publication_metadata(publication: CatalogPublication) -> dict[str, Any]:
    return {"revision": publication.revision, "status": publication.status, "digest": publication.digest}


def publication_metadata(db: Session, jurisdiction: str = DEFAULT_JURISDICTION) -> dict[str, Any]:
    return _publication_metadata(_publication(db, jurisdiction))


def _cursor(value: str) -> str | None:
    if not value:
        return None
    if len(value) > MAX_CURSOR_LENGTH:
        raise HTTPException(422, "Invalid catalog cursor")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, "Invalid catalog cursor") from None
    if not decoded or len(decoded) > MAX_CURSOR_LENGTH or any(ord(char) < 32 for char in decoded):
        raise HTTPException(422, "Invalid catalog cursor")
    return decoded


def _encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _paged(values: list[dict[str, Any]], limit: int, cursor: str) -> tuple[list[dict[str, Any]], str | None]:
    after = _cursor(cursor)
    if after is not None:
        values = [item for item in values if item["_sort_id"] > after]
    selected = values[:limit + 1]
    next_cursor = _encode(selected[limit - 1]["_sort_id"]) if len(selected) > limit else None
    selected = selected[:limit]
    for item in selected:
        item.pop("_sort_id", None)
    return selected, next_cursor


def _language(requested: str, actual: str) -> dict[str, Any]:
    return {"requested_language": requested, "content_language": actual, "fallback_used": requested != actual}


def _localized(rows: Iterable[Any], requested: str) -> tuple[Any, str] | None:
    rows = list(rows)
    for language in (requested, DEFAULT_LANGUAGE):
        for row in rows:
            if row.language == language:
                return row, language
    return None


def _json(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(503, "Public catalog unavailable") from None


def _guide(row: CatalogGuideRevision, requested: str, actual: str) -> dict[str, Any]:
    return {"id": row.guide_id, "category_id": row.category_id, "title": row.title, "summary": row.summary,
            "scenario": row.scenario, "warning_signs": _json(row.warning_signs), "safe_actions": _json(row.safe_actions),
            "recovery_guidance": _json(row.recovery_guidance), "reporting_guidance": _json(row.reporting_guidance),
            "prevention_tips": _json(row.prevention_tips), "false_positive_notes": _json(row.false_positive_notes),
            "resource_ids": _json(row.resource_ids), "lesson_ids": _json(row.lesson_ids),
            "review_status": row.review_status, "content_version": row.content_version, "language": _language(requested, actual)}


def _playbook(row: EmergencyPlaybookRevision, requested: str, actual: str) -> dict[str, Any]:
    return {"id": row.playbook_id, "title": row.title, "summary": row.summary,
            "immediate_actions": _json(row.immediate_actions), "preserve_evidence": _json(row.preserve_evidence),
            "recovery_actions": _json(row.recovery_actions), "escalation_guidance": _json(row.escalation_guidance),
            "review_status": row.review_status, "content_version": row.content_version, "language": _language(requested, actual)}


def _lesson(row: LessonRevision, requested: str, actual: str) -> dict[str, Any]:
    return {"id": row.lesson_id, "title": row.title, "summary": row.summary, "sections": _json(row.sections),
            "knowledge_checks": _json(row.knowledge_checks), "review_status": row.review_status,
            "content_version": row.content_version, "language": _language(requested, actual)}


def _checklist(row: ChecklistRevision, requested: str, actual: str) -> dict[str, Any]:
    return {"id": row.checklist_id, "title": row.title, "summary": row.summary, "items": _json(row.items),
            "review_status": row.review_status, "content_version": row.content_version, "language": _language(requested, actual)}


def _resource(row: TrustedResourceRevision, requested: str, actual: str) -> dict[str, Any]:
    return {"id": row.resource_id, "name": row.name, "jurisdiction": row.jurisdiction, "destination": row.destination,
            "publisher": row.publisher, "source_references": _json(row.source_references),
            "verification_status": row.verification_status, "verification_date": row.verification_date,
            "next_review_at": row.next_review_at, "content_digest": row.content_digest, "withdrawn": row.withdrawn,
            "language": _language(requested, actual)}


def _entries(
    db: Session,
    model: type[Any],
    id_name: str,
    revision: int,
    requested: str,
    serializer: Callable[[Any, str, str], dict[str, Any]],
    skip: Callable[[Any], bool] | None = None,
    sort_key: Callable[[dict[str, Any]], Any] | None = None,
    cursor_key: Callable[[dict[str, Any]], str] | None = None,
) -> list[dict[str, Any]]:
    id_column = getattr(model, id_name)
    rows = db.scalars(select(model).where(model.publication_revision == revision).order_by(id_column)).all()
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        grouped.setdefault(getattr(row, id_name), []).append(row)
    values: list[dict[str, Any]] = []
    for identifier, localized_rows in grouped.items():
        localized = _localized(localized_rows, requested)
        if localized is None:
            continue
        row, actual = localized
        if skip is not None and skip(row):
            continue
        value = serializer(row, requested, actual)
        value["_sort_id"] = identifier
        values.append(value)
    values.sort(key=sort_key or (lambda item: item["_sort_id"]))
    if cursor_key is not None:
        for item in values:
            item["_sort_id"] = cursor_key(item)
    return values


def _collection(
    db: Session,
    model: type[Any],
    id_name: str,
    serializer: Callable[[Any, str, str], dict[str, Any]],
    *,
    jurisdiction: str,
    language: str,
    limit: int,
    cursor: str,
    skip: Callable[[Any], bool] | None = None,
    sort_key: Callable[[dict[str, Any]], Any] | None = None,
    cursor_key: Callable[[dict[str, Any]], str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    publication = _publication(db, jurisdiction)
    values = _entries(db, model, id_name, publication.revision, language, serializer, skip, sort_key, cursor_key)
    items, next_cursor = _paged(values, limit, cursor)
    return {"items": items, "next_cursor": next_cursor}, _publication_metadata(publication)


def _detail(db: Session, model: type[Any], id_name: str, identifier: str, serializer: Callable[[Any, str, str], dict[str, Any]],
            *, jurisdiction: str, language: str, unavailable: str, skip: Callable[[Any], bool] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    publication = _publication(db, jurisdiction)
    id_column = getattr(model, id_name)
    rows = db.scalars(select(model).where(model.publication_revision == publication.revision, id_column == identifier)).all()
    localized = _localized(rows, language)
    if localized is None or (skip is not None and skip(localized[0])):
        raise HTTPException(404, unavailable)
    row, actual = localized
    return serializer(row, language, actual), _publication_metadata(publication)


def categories(db: Session, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE,
               limit: int = 20, cursor: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    def serialize(row: CatalogCategory, requested: str, actual: str) -> dict[str, Any]:
        return {"id": row.category_id, "title": row.title, "summary": row.summary, "sort_order": row.sort_order,
                "language": _language(requested, actual)}
    return _collection(
        db, CatalogCategory, "category_id", serialize, jurisdiction=jurisdiction, language=language,
        limit=limit, cursor=cursor, sort_key=lambda item: (item["sort_order"], item["_sort_id"]),
        cursor_key=lambda item: f'{item["sort_order"]:010d}:{item["_sort_id"]}',
    )


def guides(db: Session, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE,
           limit: int = 20, cursor: str = "", category_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    skip = (lambda row: category_id is not None and row.category_id != category_id) if category_id else None
    return _collection(
        db, CatalogGuideRevision, "guide_id", _guide, jurisdiction=jurisdiction, language=language,
        limit=limit, cursor=cursor, skip=skip,
    )


def guide(db: Session, guide_id: str, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE) -> tuple[dict[str, Any], dict[str, Any]]:
    return _detail(db, CatalogGuideRevision, "guide_id", guide_id, _guide, jurisdiction=jurisdiction, language=language, unavailable="Guide unavailable")


def search(db: Session, query: str, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE,
           limit: int = 20, cursor: str = "", category_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    query = query.strip()
    if not query or len(query) > MAX_SEARCH_LENGTH:
        raise HTTPException(422, "Search query is invalid")
    publication = _publication(db, jurisdiction)
    skip = (lambda row: category_id is not None and row.category_id != category_id) if category_id else None
    values = _entries(db, CatalogGuideRevision, "guide_id", publication.revision, language, _guide, skip=skip)
    needle = query.casefold()
    values = [item for item in values if needle in " ".join([item["id"], item["title"], item["summary"], item["scenario"], *item["warning_signs"]]).casefold()]
    items, next_cursor = _paged(values, limit, cursor)
    return {"items": items, "next_cursor": next_cursor}, _publication_metadata(publication)


def playbooks(db: Session, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE,
              limit: int = 20, cursor: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    return _collection(db, EmergencyPlaybookRevision, "playbook_id", _playbook, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)


def playbook(db: Session, playbook_id: str, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE) -> tuple[dict[str, Any], dict[str, Any]]:
    return _detail(db, EmergencyPlaybookRevision, "playbook_id", playbook_id, _playbook, jurisdiction=jurisdiction, language=language, unavailable="Emergency playbook unavailable")


def lessons(db: Session, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE,
            limit: int = 20, cursor: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    return _collection(db, LessonRevision, "lesson_id", _lesson, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)


def lesson(db: Session, lesson_id: str, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE) -> tuple[dict[str, Any], dict[str, Any]]:
    return _detail(db, LessonRevision, "lesson_id", lesson_id, _lesson, jurisdiction=jurisdiction, language=language, unavailable="Lesson unavailable")


def checklists(db: Session, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE,
               limit: int = 20, cursor: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    return _collection(db, ChecklistRevision, "checklist_id", _checklist, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)


def checklist(db: Session, checklist_id: str, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE) -> tuple[dict[str, Any], dict[str, Any]]:
    return _detail(db, ChecklistRevision, "checklist_id", checklist_id, _checklist, jurisdiction=jurisdiction, language=language, unavailable="Checklist unavailable")


def resources(db: Session, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE,
              limit: int = 20, cursor: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    return _collection(db, TrustedResourceRevision, "resource_id", _resource, jurisdiction=jurisdiction, language=language,
                       limit=limit, cursor=cursor, skip=lambda row: row.withdrawn)


def resource(db: Session, resource_id: str, *, jurisdiction: str = DEFAULT_JURISDICTION, language: str = DEFAULT_LANGUAGE) -> tuple[dict[str, Any], dict[str, Any]]:
    return _detail(db, TrustedResourceRevision, "resource_id", resource_id, _resource, jurisdiction=jurisdiction, language=language,
                   unavailable="Resource unavailable", skip=lambda row: row.withdrawn)


_IDENTIFIER_PATTERNS = {
    "guide": re.compile(r"^SC-[0-9]{3}$"),
    "slug": re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$"),
}


def validate_identifier(value: str, kind: str) -> None:
    pattern = _IDENTIFIER_PATTERNS.get(kind)
    if pattern is None or not pattern.fullmatch(value):
        raise HTTPException(422, "Invalid catalog identifier")


def validate_query(language: str, jurisdiction: str, limit: int, cursor: str, category_id: str | None = None) -> None:
    if language not in {"en", "hi"} or jurisdiction != DEFAULT_JURISDICTION or limit < 1 or limit > MAX_PAGE_SIZE:
        raise HTTPException(422, "Unsupported catalog language, jurisdiction or page size")
    if category_id is not None:
        validate_identifier(category_id, "slug")
    _cursor(cursor)
