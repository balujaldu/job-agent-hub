from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .state import JobStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    """ISO 8601 in UTC. SQLite returns naive datetimes, which are UTC here."""
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BaseResume(Base):
    __tablename__ = "base_resumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    file_path: Mapped[str] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON)  # ResumeData
    # Skills the user confirms they can handle, beyond what the resume lists.
    extra_skills: Mapped[list] = mapped_column(JSON, default=list)
    # Free-text notes about responsibilities at past employers.
    extra_notes: Mapped[str] = mapped_column(Text, default="")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, index=True)

    source_type: Mapped[str] = mapped_column(String(20))  # screenshot | text
    source_text: Mapped[str] = mapped_column(Text, default="")
    source_image_path: Mapped[Optional[str]] = mapped_column(String(500))

    company: Mapped[str] = mapped_column(String(300), default="")
    role: Mapped[str] = mapped_column(String(300), default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    company_website: Mapped[str] = mapped_column(String(500), default="")
    job_url: Mapped[str] = mapped_column(String(1000), default="")
    jd_text: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    recruiter_name: Mapped[str] = mapped_column(String(300), default="")

    to_email: Mapped[str] = mapped_column(String(320), default="")
    email_source: Mapped[str] = mapped_column(String(1000), default="")  # "input" or page URL
    email_subject: Mapped[str] = mapped_column(String(500), default="")
    email_body: Mapped[str] = mapped_column(Text, default="")

    tailored: Mapped[Optional[dict]] = mapped_column(JSON)  # TailoredResume
    resume_pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    ats_before: Mapped[Optional[dict]] = mapped_column(JSON)
    ats_after: Mapped[Optional[dict]] = mapped_column(JSON)

    # none | sending | sent | failed | skipped  (separate channel, separate approval)

    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AgentEvent(Base):
    __tablename__ = "agent_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(50))
    level: Mapped[str] = mapped_column(String(10), default="info")  # info | warn | error
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Secret(Base):
    """Encrypted blobs: Gmail OAuth credentials."""

    __tablename__ = "secrets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # gmail
    label: Mapped[str] = mapped_column(String(320), default="")  # Gmail address
    ciphertext: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AppSettings(Base):
    __tablename__ = "app_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    sending_paused: Mapped[bool] = mapped_column(Boolean, default=False)  # global kill switch
