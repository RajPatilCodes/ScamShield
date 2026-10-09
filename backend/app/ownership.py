from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from fastapi import Depends, HTTPException
from sqlalchemy import select, exists
from .database import get_db, begin_auth_write
from .models import User, AuthSession, Analysis
from .security import oauth2_scheme, current_user, decode_access_token


class AuthorityUnavailable(RuntimeError):
    """Deliberately contains no path, SQL, account or fencing payload."""


@contextmanager
def _authority():
    from .privacy_config import policy
    if not policy.authority_path:
        raise AuthorityUnavailable("Restoration fencing unavailable")
    try:
        # mode=rw is important: a missing ledger must never become an empty one.
        connection = sqlite3.connect(Path(policy.authority_path).resolve().as_uri() + "?mode=rw", uri=True)
    except (OSError, sqlite3.Error):
        raise AuthorityUnavailable("Restoration fencing unavailable") from None
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _payload(marker):
    from .privacy_models import DeletionMarker
    return json.dumps({column.name: getattr(marker, column.name) for column in DeletionMarker.__table__.columns},
                      sort_keys=True, separators=(",", ":"))


def _digest(rows):
    digest = hashlib.sha256()
    for payload in rows:
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _local_digest(db):
    from .privacy_models import DeletionMarker
    from .privacy_config import policy
    return _digest(_payload(row) for row in db.scalars(select(DeletionMarker).order_by(DeletionMarker.id)
                  .execution_options(yield_per=policy.batch_size)))


def _head(connection):
    head = connection.execute("SELECT authority_id,revision,digest FROM checkpoint WHERE id=1").fetchone()
    actual = _digest(row[0] for row in connection.execute("SELECT payload FROM markers ORDER BY id"))
    if not head or head[2] != actual:
        raise AuthorityUnavailable("Restoration fencing unavailable")
    return head


def require_authority(db):
    """Verify identity, monotonic checkpoint and complete local fencing contents."""
    from .privacy_models import FenceCheckpoint
    try:
        with _authority() as connection:
            head = _head(connection)
        checkpoint = db.scalar(select(FenceCheckpoint).where(FenceCheckpoint.id == 1)
                               .execution_options(populate_existing=True))
        if (not checkpoint or (checkpoint.authority_id, checkpoint.revision, checkpoint.digest) != head
                or _local_digest(db) != checkpoint.digest):
            raise AuthorityUnavailable("Restoration fencing unavailable")
    except (sqlite3.Error, OSError):
        raise AuthorityUnavailable("Restoration fencing unavailable") from None


def initialise_authority(db):
    """Explicit one-time bootstrap; refuses an existing authority or deletion state."""
    from .privacy_models import FenceCheckpoint, DeletionMarker, identifier
    from .privacy_config import policy
    begin_auth_write(db)
    if (not policy.authority_path or db.get(FenceCheckpoint, 1)
            or db.scalar(select(DeletionMarker.id).limit(1))):
        raise AuthorityUnavailable("Authority bootstrap refused")
    descriptor = os.open(policy.authority_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    authority_id, digest = identifier(), _digest(())
    with _authority() as connection:
        connection.execute("CREATE TABLE checkpoint (id INTEGER PRIMARY KEY,authority_id TEXT,revision INTEGER,digest TEXT)")
        connection.execute("CREATE TABLE markers (id TEXT PRIMARY KEY,payload TEXT NOT NULL)")
        connection.execute("INSERT INTO checkpoint VALUES (1,?,?,?)", (authority_id, 0, digest))
    db.add(FenceCheckpoint(id=1, authority_id=authority_id, revision=0, digest=digest))
    db.commit()


def publish_marker(db, marker):
    """Write authority first; an interrupted local commit leaves activation closed."""
    from .privacy_models import FenceCheckpoint
    db.flush()
    checkpoint = db.scalar(select(FenceCheckpoint).where(FenceCheckpoint.id == 1).with_for_update()
                           .execution_options(populate_existing=True))
    try:
        with _authority() as connection:
            connection.execute("BEGIN IMMEDIATE")
            head = _head(connection)
            if not checkpoint or (checkpoint.authority_id, checkpoint.revision, checkpoint.digest) != head:
                raise AuthorityUnavailable("Restoration fencing unavailable")
            connection.execute("INSERT OR REPLACE INTO markers VALUES (?,?)", (marker.id, _payload(marker)))
            digest = _digest(row[0] for row in connection.execute("SELECT payload FROM markers ORDER BY id"))
            if _local_digest(db) != digest:
                raise AuthorityUnavailable("Restoration fencing unavailable")
            checkpoint.revision += 1
            checkpoint.digest = digest
            connection.execute("UPDATE checkpoint SET revision=?,digest=? WHERE id=1", (checkpoint.revision, digest))
    except (sqlite3.Error, OSError):
        raise AuthorityUnavailable("Restoration fencing unavailable") from None


def reconcile_authority(db):
    """Import trusted intent while quarantined; preserve authoritative fencing."""
    from .privacy_models import FenceCheckpoint, DeletionMarker
    from .privacy_config import policy
    begin_auth_write(db)
    checkpoint = db.scalar(select(FenceCheckpoint).where(FenceCheckpoint.id == 1).with_for_update())
    with _authority() as connection:
        connection.execute("BEGIN IMMEDIATE")
        head = _head(connection)
        if not checkpoint or checkpoint.authority_id != head[0] or checkpoint.revision > head[1]:
            raise AuthorityUnavailable("Authority reconciliation refused")
        # Missing local markers may be restored, but unknown local intent may
        # never be discarded to accommodate a stale authority.
        for marker_id in db.scalars(select(DeletionMarker.id).execution_options(yield_per=policy.batch_size)):
            if not connection.execute("SELECT 1 FROM markers WHERE id=?", (marker_id,)).fetchone():
                raise AuthorityUnavailable("Authority reconciliation refused")
        for (payload,) in connection.execute("SELECT payload FROM markers ORDER BY id"):
            values = json.loads(payload)
            row = db.get(DeletionMarker, values["id"])
            if row is None:
                row = DeletionMarker(**values)
                db.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            db.flush()  # Release dirty/new ORM references before the next record.
        checkpoint.revision, checkpoint.digest = head[1:]
        db.flush()
        if _local_digest(db) != head[2]:
            raise AuthorityUnavailable("Authority reconciliation refused")
        # Restoration can reintroduce data even after a previously satisfied
        # purge. Reopen that intent; the authority remains the lifecycle fence.
        changed = False
        for marker in db.scalars(select(DeletionMarker).order_by(DeletionMarker.id)
                                 .execution_options(yield_per=policy.batch_size)):
            if marker.satisfied_at is not None:
                marker.satisfied_at = None
                db.flush()
                connection.execute("UPDATE markers SET payload=? WHERE id=?", (_payload(marker), marker.id))
                changed = True
        if changed:
            checkpoint.revision += 1
            checkpoint.digest = _local_digest(db)
            connection.execute("UPDATE checkpoint SET revision=?,digest=? WHERE id=1",
                               (checkpoint.revision, checkpoint.digest))
    db.commit()


@dataclass
class Owner:
    db: object
    user: User
    session: AuthSession


def locked_owner(db, user_id, lifecycle_id, session_id=None):
    user = db.scalar(select(User).where(User.id == user_id, User.lifecycle_id == lifecycle_id)
                     .with_for_update().execution_options(populate_existing=True))
    if not user or not user.is_active or user.privacy_state != "active":
        raise HTTPException(401, "Invalid or restricted account")
    from .privacy_models import fence_values
    account, generation, revision = fence_values(db, lifecycle_id)
    if account:
        raise HTTPException(401, "Invalid or restricted account")
    if revision is not None:
        user.privacy_revision = max(user.privacy_revision, revision)
    if generation is not None:
        user.data_generation = max(user.data_generation, generation + 1)
    session = None
    if session_id:
        session = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user.id)
                            .with_for_update().execution_options(populate_existing=True))
        now = int(time.time())
        if not session or session.revoked_at is not None or min(session.idle_expires_at, session.absolute_expires_at) <= now:
            raise HTTPException(401, "Invalid or expired session")
    return user, session


def write_owner(db=Depends(get_db), token=Depends(oauth2_scheme)):
    # Start before dependency reads, including on SQLite.
    begin_auth_write(db)
    user = current_user(token, db)
    user, session = locked_owner(db, user.id, user.lifecycle_id, decode_access_token(token)["sid"])
    return Owner(db, user, session)


def visible_analysis(user, now=None):
    now = int(time.time()) if now is None else now
    from .privacy_models import DeletionMarker
    fenced = exists(select(DeletionMarker.id).where(DeletionMarker.lifecycle_id == Analysis.lifecycle_id,
        ((DeletionMarker.scope == "account") | ((DeletionMarker.scope == "saved") & (Analysis.generation <= DeletionMarker.generation)) |
         ((DeletionMarker.scope == "analysis") & (Analysis.record_key == DeletionMarker.target_key)))))
    return (Analysis.user_id == user.id, Analysis.lifecycle_id == user.lifecycle_id, ~fenced,
            Analysis.generation == user.data_generation, Analysis.deleted_at.is_(None), Analysis.expires_at > now)


def owned_analysis(owner, analysis_id):
    row = owner.db.scalar(select(Analysis).where(Analysis.id == analysis_id, *visible_analysis(owner.user)))
    if row is None:
        raise HTTPException(404, "Private object not found")
    return row
