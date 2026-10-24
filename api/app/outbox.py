"""The only code that sends anything. Every send re-checks approval right before it happens."""
from __future__ import annotations

import logging

from . import gmail, render, storage
from .db import session_scope
from .events import log_event
from .models import AppSettings, Job, utcnow
from .state import JobStatus, can_send, transition

logger = logging.getLogger(__name__)


class NotAllowed(Exception):
    """Shown to the user as-is."""


def settings_for(db, user_id: int) -> AppSettings:
    s = db.get(AppSettings, user_id)
    if s is None:
        s = AppSettings(user_id=user_id)
        db.add(s)
        db.commit()
    return s


def approve_email(db, job: Job) -> None:
    """Records the user's approval. Called only from the Approve endpoint."""
    if settings_for(db, job.user_id).sending_paused:
        raise NotAllowed("Sending is paused in Settings.")
    if not job.to_email:
        raise NotAllowed("Add a recipient email address first.")
    if not gmail.connected_address(db, job.user_id):
        raise NotAllowed("Connect Gmail in Settings first.")
    job.status = transition(job.status, JobStatus.APPROVED)
    db.commit()
    log_event(db, job.id, "approval", f"You approved sending to {job.to_email}")


def send_email(job_id: int) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        if job is None or not can_send(job.status):
            logger.warning("refusing to send job %s in status %s", job_id, job and job.status)
            return
        if settings_for(db, job.user_id).sending_paused:
            job.status = transition(job.status, JobStatus.AWAITING_APPROVAL)
            db.commit()
            log_event(db, job.id, "sender", "Sending is paused; the email was not sent and needs approval again.", "warn")
            return
        job.status = transition(job.status, JobStatus.SENDING)
        db.commit()
        log_event(db, job.id, "sender", f"Sending to {job.to_email}")
        try:
            attachment = ((render.pdf_filename(job.resume_pdf_path), storage.get(job.resume_pdf_path))
                          if job.resume_pdf_path else None)
            msg_id = gmail.send(db, job.user_id, job.to_email, job.email_subject, job.email_body, attachment)
        except Exception as e:
            logger.exception("send failed for job %s", job_id)
            job.status, job.error = transition(job.status, JobStatus.FAILED), f"Email failed: {e}"
            db.commit()
            log_event(db, job.id, "sender", job.error, "error")
            return
        job.status, job.sent_at, job.error = transition(job.status, JobStatus.SENT), utcnow(), ""
        db.commit()
        log_event(db, job.id, "sender", f"Sent (Gmail id {msg_id})")
