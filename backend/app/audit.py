import time
from .privacy_config import policy, seconds
from .privacy_models import AuditEvent

EVENTS = frozenset({"consent_changed", "analysis_saved", "analysis_deleted", "deletion_requested",
                    "export_requested", "export_downloaded", "reauth_failed", "reauth_succeeded",
                    "job_completed", "job_failed", "job_retried"})


def audit(db, lifecycle_id, event, reference=None):
    if event not in EVENTS:
        raise ValueError("Audit event is not allowlisted")
    if reference is not None:
        from uuid import UUID
        if str(UUID(reference)) != reference:
            raise ValueError("Audit reference must be an opaque identifier")
    now = int(time.time())
    db.add(AuditEvent(lifecycle_id=lifecycle_id, event=event, reference=reference,
                      created_at=now, expires_at=now + seconds(policy.audit_days)))
