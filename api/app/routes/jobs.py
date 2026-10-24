from __future__ import annotations

import mimetypes
import uuid
from dataclasses import asdict
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .. import outbox, render, storage, worker
from ..ats import score_resume
from ..db import get_db
from ..deps import current_user, owned_job
from ..events import log_event
from ..models import AgentEvent, Job, User, iso
from ..pipeline import latest_resume, run_job
from ..state import InvalidTransition, JobStatus, transition
from ._files import content_disposition

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Claude API per-image limit
LOCKED = {JobStatus.APPROVED, JobStatus.SENDING, JobStatus.SENT, JobStatus.TERMINATED}


def _summary(j: Job) -> dict:
    return {
        "id": j.id, "status": j.status.value, "company": j.company, "role": j.role, "to_email": j.to_email,
        "ats_before": j.ats_before["score"] if j.ats_before else None,
        "ats_after": j.ats_after["score"] if j.ats_after else None,
        "error": j.error,
        "created_at": iso(j.created_at), "sent_at": iso(j.sent_at),
    }


def _detail(db: Session, j: Job) -> dict:
    events = db.query(AgentEvent).filter_by(job_id=j.id).order_by(AgentEvent.id).all()
    return {
        **_summary(j),
        "source_type": j.source_type, "source_text": j.source_text, "has_screenshot": bool(j.source_image_path),
        "location": j.location, "company_website": j.company_website, "job_url": j.job_url,
        "jd_text": j.jd_text, "keywords": j.keywords, "recruiter_name": j.recruiter_name,
        "email_source": j.email_source, "email_subject": j.email_subject, "email_body": j.email_body,
        "tailored": j.tailored, "has_pdf": bool(j.resume_pdf_path),
        "ats_before_detail": j.ats_before, "ats_after_detail": j.ats_after,
        "events": [{"id": e.id, "agent": e.agent, "level": e.level, "message": e.message,
                    "at": iso(e.created_at)} for e in events],
    }


@router.get("")
def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    jobs = db.query(Job).filter_by(user_id=user.id).order_by(Job.id.desc()).limit(500).all()
    return [_summary(j) for j in jobs]


@router.post("")
def create_job(text: str = Form(""), screenshot: Optional[UploadFile] = File(None),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    if latest_resume(db, user.id) is None:
        raise HTTPException(400, "Upload and confirm your base resume first.")
    text = text.strip()
    image_key = None
    if screenshot is not None and screenshot.filename:
        ext = IMAGE_TYPES.get(screenshot.content_type or "")
        if not ext:
            raise HTTPException(400, "Screenshots must be PNG, JPEG, WebP or GIF.")
        data = screenshot.file.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(400, "Screenshots must be 5 MB or smaller.")
        image_key = storage.put(f"uploads/job-{uuid.uuid4().hex}{ext}", data, screenshot.content_type or "image/png")
    if not text and image_key is None:
        raise HTTPException(400, "Add a screenshot or paste the job description.")
    job = Job(user_id=user.id, source_type="screenshot" if image_key else "text", source_text=text,
              source_image_path=image_key, status=JobStatus.QUEUED)
    db.add(job)
    db.commit()
    log_event(db, job.id, "pipeline", "Queued")
    worker.submit(run_job, job.id)
    return _summary(job)


@router.get("/{job_id}")
def get_job(job: Job = Depends(owned_job), db: Session = Depends(get_db)):
    return _detail(db, job)


class JobEdit(BaseModel):
    to_email: Optional[EmailStr] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None


@router.patch("/{job_id}")
def edit_job(body: JobEdit, job: Job = Depends(owned_job), db: Session = Depends(get_db)):
    if job.status in LOCKED or job.status in (JobStatus.QUEUED, JobStatus.PROCESSING):
        raise HTTPException(409, f"Can't edit a job that is {job.status.value.replace('_', ' ')}.")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is not None:
            setattr(job, field, str(value).strip() if field != "email_body" else value)
    if body.to_email:
        job.email_source = "entered by you"
        if job.status == JobStatus.EMAIL_NOT_FOUND:
            job.status = transition(job.status, JobStatus.AWAITING_APPROVAL)
    db.commit()
    log_event(db, job.id, "you", "Edited " + ", ".join(k.replace("_", " ") for k in changes))
    return _detail(db, job)


class TailoredEdit(BaseModel):
    tailored: dict


@router.put("/{job_id}/tailored")
def edit_tailored(body: TailoredEdit, job: Job = Depends(owned_job), db: Session = Depends(get_db)):
    """Accepts removals and edits of bullets/skills. Employers, titles, dates and education
    are always restored from the existing version so they can't drift."""
    if job.status in LOCKED or not job.tailored:
        raise HTTPException(409, "This resume can no longer be edited.")
    new, old = body.tailored, job.tailored
    try:
        experience = []
        for i, e in enumerate(old["experience"]):
            bullets = new["experience"][i]["bullets"]
            experience.append({**e, "bullets": [{"text": str(b["text"]).strip(), "provenance": b["provenance"]}
                                                for b in bullets if str(b["text"]).strip()]})
        projects = []
        for i, p in enumerate(old.get("projects", [])):
            bullets = new["projects"][i]["bullets"]
            projects.append({**p, "bullets": [{"text": str(b["text"]).strip(), "provenance": b["provenance"]}
                                              for b in bullets if str(b["text"]).strip()]})
        skills = [{"name": str(s["name"]).strip(), "provenance": s["provenance"]}
                  for s in new["skills"] if str(s["name"]).strip()]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(400, "Unexpected resume shape.")
    tailored = {**old, "summary": str(new.get("summary", old["summary"])).strip(),
                "skills": skills, "experience": experience, "projects": projects}
    job.tailored = tailored
    job.ats_after = asdict(score_resume(render.to_text(tailored), job.jd_text, job.keywords))
    storage.put(job.resume_pdf_path, render.to_pdf(tailored), "application/pdf")
    db.commit()
    log_event(db, job.id, "you", f"Edited the tailored resume; ATS score now {job.ats_after['score']}/100")
    return _detail(db, job)


@router.post("/{job_id}/approve-email")
def approve_email(job: Job = Depends(owned_job), db: Session = Depends(get_db)):
    try:
        outbox.approve_email(db, job)
    except outbox.NotAllowed as e:
        raise HTTPException(409, str(e))
    except InvalidTransition:
        raise HTTPException(409, f"A job that is {job.status.value.replace('_', ' ')} can't be approved.")
    worker.submit(outbox.send_email, job.id)
    return _detail(db, job)


@router.post("/{job_id}/terminate")
def terminate(job: Job = Depends(owned_job), db: Session = Depends(get_db)):
    try:
        job.status = transition(job.status, JobStatus.TERMINATED)
    except InvalidTransition:
        raise HTTPException(409, f"A job that is {job.status.value.replace('_', ' ')} can't be terminated.")
    db.commit()
    log_event(db, job.id, "you", "Terminated the job")
    return _detail(db, job)


class Retry(BaseModel):
    mode: Literal["reprocess", "resend"] = "reprocess"


@router.post("/{job_id}/retry")
def retry(body: Retry, job: Job = Depends(owned_job), db: Session = Depends(get_db)):
    if job.status != JobStatus.FAILED:
        raise HTTPException(409, "Only failed jobs can be retried.")
    if body.mode == "resend":
        if not (job.to_email and job.email_body and job.resume_pdf_path):
            raise HTTPException(409, "This job has no finished drafts; reprocess it instead.")
        job.status = transition(job.status, JobStatus.AWAITING_APPROVAL)
        db.commit()
        log_event(db, job.id, "you", "Back to awaiting approval for another send attempt")
        return _detail(db, job)
    job.status = transition(job.status, JobStatus.QUEUED)
    job.error = ""
    db.commit()
    log_event(db, job.id, "you", "Reprocessing")
    worker.submit(run_job, job.id)
    return _detail(db, job)


@router.get("/{job_id}/resume.pdf")
def resume_pdf(download: bool = False, job: Job = Depends(owned_job)):
    try:
        data = storage.get(job.resume_pdf_path) if job.resume_pdf_path else None
    except FileNotFoundError:
        data = None
    if data is None:
        raise HTTPException(404, "No resume generated yet")
    return Response(data, media_type="application/pdf", headers={
        "Content-Disposition": content_disposition(render.pdf_filename(job.resume_pdf_path), inline=not download),
        "Cache-Control": "no-store"})


@router.get("/{job_id}/screenshot")
def screenshot(job: Job = Depends(owned_job)):
    try:
        data = storage.get(job.source_image_path) if job.source_image_path else None
    except FileNotFoundError:
        data = None
    if data is None:
        raise HTTPException(404, "No screenshot")
    return Response(data, media_type=mimetypes.guess_type(job.source_image_path)[0] or "image/png")
