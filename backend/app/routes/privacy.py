import time
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from .. import privacy as service
from ..database import get_db, begin_auth_write
from ..ownership import write_owner, owned_analysis
from ..privacy_config import policy
from ..privacy_models import PrivacyJob
from ..privacy_rate_limits import check, private_digest
from ..privacy_schemas import (ConsentRequest, SaveRequest, ReauthRequest, ExportRequest,
                              DeletionRequest, ReceiptRequest, AnalysisDeleteRequest)
from ..recent_auth import issue, consume
from ..privacy_jobs import stream_export
from ..audit import audit

router = APIRouter(prefix="/v1/privacy", tags=["privacy"])


def ip(request):
    return request.client.host if request.client else "unknown"


@router.get("")
def settings(owner=Depends(write_owner)):
    return service.settings(owner)


@router.put("/consents/{purpose}")
def consent(purpose: str, body: ConsentRequest, owner=Depends(write_owner), key: str = Header(alias="Idempotency-Key")):
    return service.change_consent(owner, purpose, body, key)


@router.post("/reauthenticate")
def reauthenticate(body: ReauthRequest, request: Request, owner=Depends(write_owner)):
    return issue(owner, body, ip(request))


@router.post("/analyses", status_code=201)
def save(body: SaveRequest, owner=Depends(write_owner), key: str = Header(alias="Idempotency-Key")):
    return service.save(owner, body, key)


@router.get("/analyses/{analysis_id}")
def detail(analysis_id: int, owner=Depends(write_owner)):
    return service.serialize_analysis(owned_analysis(owner, analysis_id))


@router.delete("/analyses/{analysis_id}", status_code=202)
def delete_one(analysis_id: int, body: AnalysisDeleteRequest, request: Request, owner=Depends(write_owner),
               key: str = Header(alias="Idempotency-Key")):
    return service.delete_one(owner, analysis_id, body, key, ip(request))


@router.post("/exports", status_code=202)
def export(body: ExportRequest, request: Request, owner=Depends(write_owner), key: str = Header(alias="Idempotency-Key")):
    return service.create_export(owner, body, key, ip(request))


@router.get("/exports")
def exports(request: Request, owner=Depends(write_owner), cursor: str = Query("", max_length=36)):
    service.rate(owner, "export_read", ip(request), policy.export_read_limit)
    rows = owner.db.scalars(select(PrivacyJob).where(PrivacyJob.lifecycle_id == owner.user.lifecycle_id,
        PrivacyJob.user_id == owner.user.id, PrivacyJob.kind == "export", PrivacyJob.id > cursor,
        (PrivacyJob.status_expires_at.is_(None) | (PrivacyJob.status_expires_at > int(time.time()))))
        .order_by(PrivacyJob.id).limit(policy.batch_size)).all()
    return {"items": [service.job_status(row) for row in rows], "next_cursor": rows[-1].id if len(rows) == policy.batch_size else None}


@router.get("/exports/{job_id}")
def export_status(job_id: str, request: Request, owner=Depends(write_owner)):
    service.rate(owner, "export_read", ip(request), policy.export_read_limit)
    return service.job_status(service.owned_job(owner, job_id, "export"))


@router.get("/exports/{job_id}/content")
def content(job_id: str, request: Request, owner=Depends(write_owner), grant: str = Header(alias="X-Recent-Auth")):
    service.rate(owner, "export_read", ip(request), policy.export_read_limit)
    job = service.owned_job(owner, job_id, "export")
    now = int(time.time())
    if (job.state != "ready" or job.revision != owner.user.privacy_revision or job.staging_expires_at <= now
        or (job.source_expires_at is not None and job.source_expires_at <= now)):
        raise HTTPException(410, "Export unavailable")
    consume(owner, grant, "export_download", job_id)
    audit(owner.db, owner.user.lifecycle_id, "export_downloaded", job.id)
    owner.db.commit()
    token = request.headers["authorization"].split(" ", 1)[1]
    return StreamingResponse(stream_export(job_id, owner.user.id, owner.user.lifecycle_id, owner.session.id, token),
        media_type="application/x-ndjson", headers={"Content-Disposition": 'attachment; filename="scamshield-export.jsonl"',
                                                   "Content-Length": str(job.total_bytes)})


@router.post("/deletions", status_code=202)
def deletion(body: DeletionRequest, request: Request, owner=Depends(write_owner), key: str = Header(alias="Idempotency-Key")):
    return service.delete_data(owner, body, key, ip(request))


@router.get("/deletions/{job_id}")
def deletion_status(job_id: str, request: Request, owner=Depends(write_owner)):
    service.rate(owner, "receipt", ip(request), policy.receipt_limit)
    return service.job_status(service.owned_job(owner, job_id, "deletion"))


@router.post("/deletions/status")
def receipt_status(body: ReceiptRequest, request: Request, db=Depends(get_db)):
    begin_auth_write(db)
    job = db.scalar(select(PrivacyJob).where(PrivacyJob.receipt_digest == private_digest(body.receipt), PrivacyJob.kind == "deletion"))
    if not job or (job.status_expires_at is not None and job.status_expires_at <= int(time.time())):
        check(db, "receipt", "unbound-receipt", ip(request), policy.receipt_limit)
        db.commit()
        raise HTTPException(404, "Status unavailable")
    check(db, "receipt", job.lifecycle_id, ip(request), policy.receipt_limit)
    result = service.job_status(job)
    db.commit()
    return result
