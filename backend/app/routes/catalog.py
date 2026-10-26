from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from .. import catalog
from ..catalog_config import DEFAULT_JURISDICTION, DEFAULT_LANGUAGE, DEFAULT_PAGE_SIZE
from ..catalog_schemas import CategoryPage, ChecklistPage, ChecklistResponse, EmergencyPage, EmergencyPlaybookResponse, GuidePage, GuideResponse, LessonPage, LessonResponse, ResourcePage, ResourceResponse, SearchResponse
from ..database import get_db


router = APIRouter(prefix="/v1", tags=["public catalog"])


def _headers(response: Response, metadata: dict[str, object]) -> None:
    revision = metadata["revision"]
    digest = metadata["digest"]
    response.headers["X-Catalog-Revision"] = str(revision)
    response.headers["X-Catalog-Status"] = str(metadata["status"])
    response.headers["X-Catalog-Digest"] = str(digest)
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["ETag"] = f'"catalog-{revision}-{str(digest)[:16]}"'


def _query(language: str, jurisdiction: str, limit: int, cursor: str, category_id: str | None = None) -> None:
    catalog.validate_query(language, jurisdiction, limit, cursor, category_id)


@router.get("/catalog/categories", response_model=CategoryPage)
def category_list(response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION),
                  limit: int = Query(DEFAULT_PAGE_SIZE), cursor: str = Query("", max_length=256), db: Session = Depends(get_db)):
    _query(language, jurisdiction, limit, cursor)
    body, metadata = catalog.categories(db, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)
    _headers(response, metadata)
    return body


@router.get("/catalog/guides", response_model=GuidePage)
def guide_list(response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION),
               limit: int = Query(DEFAULT_PAGE_SIZE), cursor: str = Query("", max_length=256), category_id: str | None = Query(None, max_length=40), db: Session = Depends(get_db)):
    _query(language, jurisdiction, limit, cursor, category_id)
    body, metadata = catalog.guides(db, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor, category_id=category_id)
    _headers(response, metadata)
    return body


@router.get("/catalog/guides/{guide_id}", response_model=GuideResponse)
def guide_detail(guide_id: str, response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION), db: Session = Depends(get_db)):
    _query(language, jurisdiction, DEFAULT_PAGE_SIZE, "")
    catalog.validate_identifier(guide_id, "guide")
    body, metadata = catalog.guide(db, guide_id, jurisdiction=jurisdiction, language=language)
    _headers(response, metadata)
    return body


@router.get("/catalog/search", response_model=SearchResponse)
def guide_search(response: Response, q: str = Query(..., max_length=100), language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION),
                 limit: int = Query(DEFAULT_PAGE_SIZE), cursor: str = Query("", max_length=256), category_id: str | None = Query(None, max_length=40), db: Session = Depends(get_db)):
    _query(language, jurisdiction, limit, cursor, category_id)
    body, metadata = catalog.search(db, q, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor, category_id=category_id)
    _headers(response, metadata)
    return body


@router.get("/emergency/playbooks", response_model=EmergencyPage)
def playbook_list(response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION),
                  limit: int = Query(DEFAULT_PAGE_SIZE), cursor: str = Query("", max_length=256), db: Session = Depends(get_db)):
    _query(language, jurisdiction, limit, cursor)
    body, metadata = catalog.playbooks(db, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)
    _headers(response, metadata)
    return body


@router.get("/emergency/playbooks/{playbook_id}", response_model=EmergencyPlaybookResponse)
def playbook_detail(playbook_id: str, response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION), db: Session = Depends(get_db)):
    _query(language, jurisdiction, DEFAULT_PAGE_SIZE, "")
    catalog.validate_identifier(playbook_id, "slug")
    body, metadata = catalog.playbook(db, playbook_id, jurisdiction=jurisdiction, language=language)
    _headers(response, metadata)
    return body


@router.get("/learning/lessons", response_model=LessonPage)
def lesson_list(response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION),
                limit: int = Query(DEFAULT_PAGE_SIZE), cursor: str = Query("", max_length=256), db: Session = Depends(get_db)):
    _query(language, jurisdiction, limit, cursor)
    body, metadata = catalog.lessons(db, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)
    _headers(response, metadata)
    return body


@router.get("/learning/lessons/{lesson_id}", response_model=LessonResponse)
def lesson_detail(lesson_id: str, response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION), db: Session = Depends(get_db)):
    _query(language, jurisdiction, DEFAULT_PAGE_SIZE, "")
    catalog.validate_identifier(lesson_id, "slug")
    body, metadata = catalog.lesson(db, lesson_id, jurisdiction=jurisdiction, language=language)
    _headers(response, metadata)
    return body


@router.get("/checklists", response_model=ChecklistPage)
def checklist_list(response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION),
                   limit: int = Query(DEFAULT_PAGE_SIZE), cursor: str = Query("", max_length=256), db: Session = Depends(get_db)):
    _query(language, jurisdiction, limit, cursor)
    body, metadata = catalog.checklists(db, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)
    _headers(response, metadata)
    return body


@router.get("/checklists/{checklist_id}", response_model=ChecklistResponse)
def checklist_detail(checklist_id: str, response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION), db: Session = Depends(get_db)):
    _query(language, jurisdiction, DEFAULT_PAGE_SIZE, "")
    catalog.validate_identifier(checklist_id, "slug")
    body, metadata = catalog.checklist(db, checklist_id, jurisdiction=jurisdiction, language=language)
    _headers(response, metadata)
    return body


@router.get("/resources", response_model=ResourcePage)
def resource_list(response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION),
                  limit: int = Query(DEFAULT_PAGE_SIZE), cursor: str = Query("", max_length=256), db: Session = Depends(get_db)):
    _query(language, jurisdiction, limit, cursor)
    body, metadata = catalog.resources(db, jurisdiction=jurisdiction, language=language, limit=limit, cursor=cursor)
    _headers(response, metadata)
    return body


@router.get("/resources/{resource_id}", response_model=ResourceResponse)
def resource_detail(resource_id: str, response: Response, language: Literal["en", "hi"] = Query(DEFAULT_LANGUAGE), jurisdiction: str = Query(DEFAULT_JURISDICTION), db: Session = Depends(get_db)):
    _query(language, jurisdiction, DEFAULT_PAGE_SIZE, "")
    catalog.validate_identifier(resource_id, "slug")
    body, metadata = catalog.resource(db, resource_id, jurisdiction=jurisdiction, language=language)
    _headers(response, metadata)
    return body
