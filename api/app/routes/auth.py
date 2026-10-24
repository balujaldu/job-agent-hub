from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_user
from ..models import Secret, User
from ..security import SESSION_COOKIE, SESSION_DAYS, hash_password, session_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


def _set_session(response: Response, user: User) -> None:
    response.set_cookie(
        SESSION_COOKIE, session_token(user.id), max_age=SESSION_DAYS * 86400,
        httponly=True, samesite="lax", secure=get_settings().cookie_secure,
    )


@router.get("/status")
def status(db: Session = Depends(get_db)):
    has_user = db.query(User).count() > 0
    return {"has_user": has_user, "signups_open": not has_user or get_settings().allow_signups}


@router.post("/register")
def register(body: Credentials, response: Response, db: Session = Depends(get_db)):
    # Only the first account can be created unless ALLOW_SIGNUPS is on.
    if db.query(User).count() > 0 and not get_settings().allow_signups:
        raise HTTPException(403, "An account already exists. Sign in instead.")
    if db.query(User).filter_by(email=body.email.lower()).count():
        raise HTTPException(409, "That email already has an account. Sign in instead.")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    _set_session(response, user)
    return {"email": user.email}


@router.post("/login")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.lower()).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    _set_session(response, user)
    return {"email": user.email}


@router.post("/reset-password")
def reset_password(body: Credentials, response: Response, db: Session = Depends(get_db)):
    """Forgot password: set a new one and sign in. By design nobody verifies the caller (the app is
    for a few friends), so the connected Gmail account is disconnected to keep a reset from being
    a way to send as someone else. The real owner reconnects it."""
    user = db.query(User).filter_by(email=body.email.lower()).one_or_none()
    if user is None:
        raise HTTPException(404, "No account with that email.")
    user.password_hash = hash_password(body.password)
    db.query(Secret).filter_by(user_id=user.id, kind="gmail").delete()
    db.commit()
    _set_session(response, user)
    return {"email": user.email}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email}
