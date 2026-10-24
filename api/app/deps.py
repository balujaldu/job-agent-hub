from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import Job, User
from .security import SESSION_COOKIE, unsign


def current_user(session: str = Cookie(default="", alias=SESSION_COOKIE), db: Session = Depends(get_db)) -> User:
    payload = unsign(session) if session else None
    user = db.get(User, int(payload["sub"])) if payload and payload.get("typ") == "session" else None
    if user is None:
        raise HTTPException(401, "Not signed in")
    return user


def owned_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "Job not found")
    return job
