"""Runs the agents for one job, from raw input to drafts awaiting approval. Never sends."""
from __future__ import annotations

import logging
import mimetypes
from dataclasses import asdict

from sqlalchemy.orm import Session

from . import render, storage
from .agents import composer, email_finder, extractor, tailor
from .ats import score_resume
from .db import session_scope
from .events import log_event
from .llm import LLMError
from .models import BaseResume, Job
from .schemas import ResumeData
from .state import JobStatus, transition

logger = logging.getLogger(__name__)


class Stopped(Exception):
    """The user terminated the job while it was processing."""


def latest_resume(db: Session, user_id: int) -> BaseResume | None:
    return (db.query(BaseResume).filter_by(user_id=user_id, confirmed=True)
            .order_by(BaseResume.id.desc()).first())


def _checkpoint(db: Session, job: Job) -> None:
    db.commit()
    db.refresh(job)
    if job.status == JobStatus.TERMINATED:
        raise Stopped()


def _pick_input_email(emails: list, company_website: str) -> str:
    """Prefer a hiring-looking address on the company's domain among those in the posting."""
    domain = ""
    if company_website:
        from urllib.parse import urlparse

        host = urlparse(email_finder.normalize_url(company_website)).hostname or ""
        domain = email_finder._root_domain(host) if host else ""
    ranked = sorted(emails, key=lambda e: -email_finder.score_email(e, domain, ""))
    usable = [e for e in ranked if email_finder.score_email(e, domain, "") > -100]
    return usable[0] if usable else ""


def run_job(job_id: int) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        if job is None or job.status != JobStatus.QUEUED:
            return
        job.status = transition(job.status, JobStatus.PROCESSING)
        job.error = ""
        db.commit()
        try:
            _run(db, job)
        except Stopped:
            log_event(db, job.id, "pipeline", "Stopped: the job was terminated.", "warn")
        except LLMError as e:
            db.rollback()
            job.status, job.error = JobStatus.FAILED, str(e)
            db.commit()
            log_event(db, job.id, "pipeline", f"Failed: {e}", "error")
        except Exception as e:  # keep the worker alive; surface a readable error
            logger.exception("job %s failed", job_id)
            db.rollback()
            job.status, job.error = JobStatus.FAILED, f"Unexpected error: {e.__class__.__name__}: {e}"
            db.commit()
            log_event(db, job.id, "pipeline", job.error, "error")


def _run(db: Session, job: Job) -> None:
    base_row = latest_resume(db, job.user_id)
    if base_row is None:
        raise LLMError("Upload and confirm your base resume first.")
    base = ResumeData.model_validate(base_row.data)

    # 1. Extract
    log_event(db, job.id, "extractor", "Reading the job posting" + (" screenshot" if job.source_image_path else ""))
    image = media_type = None
    if job.source_image_path:
        image = storage.get(job.source_image_path)
        media_type = mimetypes.guess_type(job.source_image_path)[0] or "image/png"
    ex = extractor.extract_job(job.source_text, image, media_type or "image/png")
    job.company, job.role, job.location = ex.company, ex.role, ex.location
    job.company_website, job.job_url, job.jd_text = ex.company_website, ex.job_url, ex.jd_text
    job.recruiter_name, job.keywords = ex.recruiter_name, ex.keywords
    log_event(db, job.id, "extractor",
              f"Found {ex.role or 'a role'} at {ex.company or 'unknown company'}; "
              f"{len(ex.keywords)} ATS keywords; {len(ex.emails)} email(s) in the posting")
    _checkpoint(db, job)

    # 2. Score the base resume, then tailor
    before = score_resume(base_row.raw_text, job.jd_text, job.keywords)
    job.ats_before = asdict(before)
    log_event(db, job.id, "ats", f"Base resume scores {before.score}/100; {len(before.missing)} keywords missing")
    log_event(db, job.id, "tailor", "Tailoring the resume to the job description")
    out = tailor.tailor(base, base_row.extra_skills or [], base_row.extra_notes or "",
                        job.jd_text, job.keywords, before.missing)
    tailored = tailor.assemble(base, out, base_row.extra_skills or [])
    after = score_resume(render.to_text(tailored), job.jd_text, job.keywords)
    job.tailored, job.ats_after = tailored, asdict(after)
    inferred = sum(b["provenance"] == "inferred" for e in tailored["experience"] for b in e["bullets"])
    inferred += sum(s["provenance"] == "inferred" for s in tailored["skills"])
    log_event(db, job.id, "tailor",
              f"Tailored resume scores {after.score}/100 (was {before.score}); "
              f"{inferred} inferred item(s) highlighted for review")
    _checkpoint(db, job)

    job.resume_pdf_path = storage.put(render.pdf_key(job.id, base.name), render.to_pdf(tailored), "application/pdf")
    log_event(db, job.id, "renderer", "Rendered the ATS-safe PDF")
    _checkpoint(db, job)

    # 3. Recipient
    email = _pick_input_email(ex.emails, job.company_website)
    if email:
        job.to_email, job.email_source = email, "input"
        log_event(db, job.id, "email_finder", f"Using {email} from the posting")
    else:
        result, website = email_finder.find_hiring_email(
            job.company, job.company_website, lambda m: log_event(db, job.id, "email_finder", m))
        if website:
            job.company_website = website
        if result.email:
            job.to_email, job.email_source = result.email, result.source
            log_event(db, job.id, "email_finder", f"Found {result.email} on {result.source}")
        else:
            alts = ", ".join(c.email for c in result.alternatives)
            log_event(db, job.id, "email_finder",
                      f"{result.note or 'No hiring email found.'} Checked {len(result.pages_checked)} page(s)."
                      + (f" Other addresses on the site: {alts}" if alts else ""), "warn")
    _checkpoint(db, job)

    # 4. Drafts
    log_event(db, job.id, "composer", "Drafting the application email")
    drafts = composer.compose(
        {"company": job.company, "role": job.role, "location": job.location, "job_url": job.job_url,
         "recruiter_name": job.recruiter_name, "jd_excerpt": job.jd_text[:3000]},
        tailored,
    )
    job.email_subject, job.email_body = drafts.email_subject, drafts.email_body
    log_event(db, job.id, "composer", "Drafts ready")
    _checkpoint(db, job)

    final = transition(job.status, JobStatus.AWAITING_APPROVAL if job.to_email else JobStatus.EMAIL_NOT_FOUND)
    # Conditional update: a Terminate clicked during this last step must win.
    updated = (db.query(Job).filter(Job.id == job.id, Job.status == JobStatus.PROCESSING)
               .update({Job.status: final}, synchronize_session=False))
    db.commit()
    if not updated:
        raise Stopped()
    log_event(db, job.id, "pipeline",
              "Waiting for your approval" if job.to_email else
              "No email found. The resume and drafts are ready; add an address to send, or send them yourself")
