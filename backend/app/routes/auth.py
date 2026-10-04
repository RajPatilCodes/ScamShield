import time
import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..auth_rate_limit import check_limit, record_attempt
from ..database import begin_auth_write, get_db
from ..models import AuthSession, User
from ..recovery import consume_challenge, send_challenge
from ..schemas import ChallengeRequest, Credentials, EmailRequest, RecoveryRequest, RefreshRequest, Token
from ..security import current_user, hash_password, password_needs_rehash, verify_password
from ..sessions import create_session, rotate_refresh

router = APIRouter(prefix="/v1/auth", tags=["auth"])
GENERIC = {"message": "If eligible, check your email for further instructions."}


@router.post("/register", status_code=201)
def register(credentials: Credentials, db: Session = Depends(get_db)):
    begin_auth_write(db)
    user = db.scalar(select(User).where(User.email == credentials.email.lower()))
    if not user:
        user = User(email=credentials.email.lower(), password_hash=hash_password(credentials.password))
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            if db.scalar(select(User).where(User.email == credentials.email.lower())):
                return GENERIC
            raise HTTPException(status_code=503, detail="Registration unavailable") from None
        send_challenge(db, user, "verification")
    db.commit()
    return GENERIC


@router.post("/login", response_model=Token)
def login(credentials: Credentials, request: Request, db: Session = Depends(get_db)):
    begin_auth_write(db)
    ip = request.client.host if request.client else "unknown"
    email = credentials.email.lower()
    check_limit(db, "login", email, ip, 5)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    valid = verify_password(credentials.password, user.password_hash) if user else verify_password(credentials.password, _cached_dummy_hash())
    if not valid or not user or not user.is_active or not user.email_verified:
        record_attempt(db, "login", email, ip)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(credentials.password)
    token = create_session(db, user)
    db.commit()
    return token


@lru_cache(maxsize=1)
def _cached_dummy_hash():
    return hash_password("synthetic-dummy-password-not-an-account")


@router.post("/refresh", response_model=Token)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    return rotate_refresh(db, body.refresh_token)


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    # Possession of the durable credential authorizes only revocation, never access.
    from ..models import RefreshCredential
    from ..sessions import credential_digest
    begin_auth_write(db)
    credential = db.get(RefreshCredential, credential_digest(body.refresh_token))
    if credential:
        db.execute(update(AuthSession).where(AuthSession.id == credential.session_id, AuthSession.revoked_at.is_(None))
                   .values(revoked_at=int(time.time())))
    db.commit()
    return Response(status_code=204)


@router.get("/sessions")
def sessions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = int(time.time())
    rows = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None), AuthSession.idle_expires_at > now, AuthSession.absolute_expires_at > now))
    return {"items": [{"id": row.id, "created_at": row.created_at, "idle_expires_at": row.idle_expires_at,
                       "absolute_expires_at": row.absolute_expires_at} for row in rows]}


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    db.execute(update(AuthSession).where(AuthSession.id == row.id, AuthSession.user_id == user.id)
               .values(revoked_at=int(time.time())))
    db.commit()
    return Response(status_code=204)


def request_challenge(body, request, db, purpose):
    begin_auth_write(db)
    email = body.email.lower()
    ip = request.client.host if request.client else "unknown"
    check_limit(db, "challenge", email, ip, 3)
    record_attempt(db, "challenge", email, ip)
    db.commit()
    begin_auth_write(db)
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user and user.is_active and (purpose == "recovery" or not user.email_verified):
        try:
            send_challenge(db, user, purpose)
        except HTTPException as error:
            if error.status_code != 503:
                raise
            # A transport outage must not turn recovery into an account oracle.
            db.rollback()
            logging.getLogger(__name__).warning("Authentication challenge delivery unavailable")
    db.commit()
    return GENERIC


@router.post("/verification/request", status_code=202)
def verification_request(body: EmailRequest, request: Request, db: Session = Depends(get_db)):
    return request_challenge(body, request, db, "verification")


@router.post("/verification/confirm", status_code=204)
def verification_confirm(body: ChallengeRequest, db: Session = Depends(get_db)):
    begin_auth_write(db)
    consume_challenge(db, body.token, "verification")
    db.commit()
    return Response(status_code=204)


@router.post("/recovery/request", status_code=202)
def recovery_request(body: EmailRequest, request: Request, db: Session = Depends(get_db)):
    return request_challenge(body, request, db, "recovery")


@router.post("/recovery/confirm", status_code=204)
def recovery_confirm(body: RecoveryRequest, db: Session = Depends(get_db)):
    begin_auth_write(db)
    consume_challenge(db, body.token, "recovery", body.password)
    db.commit()
    return Response(status_code=204)
