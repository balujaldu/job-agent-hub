from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..agents import resume_reader
from ..db import get_db
from ..deps import current_user
from ..llm import LLMError
from ..models import BaseResume, User
from ..schemas import ResumeData
from ._files import content_disposition

router = APIRouter(prefix="/api/resume", tags=["resume"])
MAX_BYTES = 10 * 1024 * 1024


def _out(r: BaseResume) -> dict:
    return {"id": r.id, "filename": r.filename, "data": r.data, "extra_skills": r.extra_skills or [],
            "extra_notes": r.extra_notes or "", "confirmed": r.confirmed}


@router.get("")
def get_resume(user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(BaseResume).filter_by(user_id=user.id).order_by(BaseResume.id.desc()).first()
    return _out(r) if r else None


@router.post("")
def upload(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(400, "Upload a PDF or DOCX file.")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "The file is larger than 10 MB.")
    try:
        text = resume_reader.extract_text(data, suffix)
        parsed = resume_reader.parse_resume(data, suffix, text)
    except (ValueError, LLMError) as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(422, "Couldn't read that file. Is it a valid PDF or DOCX?")
    key = storage.put(f"uploads/resume-{uuid.uuid4().hex}{suffix}", data,
                      mimetypes.guess_type(f"x{suffix}")[0] or "application/octet-stream")
    r = BaseResume(user_id=user.id, filename=file.filename or Path(key).name, file_path=key,
                   raw_text=text, data=parsed.model_dump(), extra_skills=[], extra_notes="", confirmed=False)
    db.add(r)
    db.commit()
    return _out(r)


class ResumeUpdate(BaseModel):
    data: ResumeData
    extra_skills: List[str] = Field(default_factory=list)
    extra_notes: str = ""
    confirmed: bool = True


@router.put("/{resume_id}")
def update(resume_id: int, body: ResumeUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(BaseResume, resume_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    r.data = body.data.model_dump()
    r.extra_skills = [s.strip() for s in body.extra_skills if s.strip()]
    r.extra_notes = body.extra_notes.strip()
    r.confirmed = body.confirmed
    db.commit()
    return _out(r)


@router.get("/{resume_id}/file")
def original_file(resume_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(BaseResume, resume_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    try:
        data = storage.get(r.file_path)
    except FileNotFoundError:
        raise HTTPException(404, "The original file is no longer available.")
    return Response(data, media_type=mimetypes.guess_type(r.filename)[0] or "application/octet-stream",
                    headers={"Content-Disposition": content_disposition(r.filename, inline=False)})
