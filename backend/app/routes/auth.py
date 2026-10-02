from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import Credentials, Token
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=201)
def register(credentials: Credentials, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == credentials.email.lower())):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=credentials.email.lower(), password_hash=hash_password(credentials.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_token(user.id))


@router.post("/login", response_model=Token)
def login(credentials: Credentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == credentials.email.lower()))
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return Token(access_token=create_token(user.id))
