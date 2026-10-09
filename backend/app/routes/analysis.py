from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Analysis, User
from ..schemas import AnalysisResponse
from ..scoring import analyze
from ..security import current_user
from ..ownership import visible_analysis
from ..privacy_schemas import TransientRequest, SavedHistoryResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_content(request: TransientRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    score, verdict, flags = analyze(request.content)
    return AnalysisResponse(score=score, verdict=verdict, flags=flags)


@router.get("/history", response_model=SavedHistoryResponse)
def analysis_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    filters = list(visible_analysis(user))
    if search and search.strip():
        filters.append(Analysis.content.ilike(f"%{search.strip()}%"))
    total = db.scalar(select(func.count()).select_from(Analysis).where(*filters)) or 0
    rows = db.scalars(
        select(Analysis).where(*filters).order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return SavedHistoryResponse(items=rows, page=page, page_size=page_size, total=total)
