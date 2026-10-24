"""Job state machine. The only place that decides whether a send is allowed."""
from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    EMAIL_NOT_FOUND = "email_not_found"
    APPROVED = "approved"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    TERMINATED = "terminated"


TERMINAL = {JobStatus.SENT, JobStatus.TERMINATED}

_ALLOWED = {
    JobStatus.QUEUED: {JobStatus.PROCESSING, JobStatus.TERMINATED},
    JobStatus.PROCESSING: {
        JobStatus.AWAITING_APPROVAL,
        JobStatus.EMAIL_NOT_FOUND,
        JobStatus.FAILED,
        JobStatus.TERMINATED,
    },
    JobStatus.AWAITING_APPROVAL: {JobStatus.APPROVED, JobStatus.TERMINATED},
    # No address: the user can type one in (which still needs approval), or terminate.
    JobStatus.EMAIL_NOT_FOUND: {JobStatus.AWAITING_APPROVAL, JobStatus.TERMINATED},
    # Approval can be withdrawn (e.g. sending paused) before the send starts.
    JobStatus.APPROVED: {JobStatus.SENDING, JobStatus.AWAITING_APPROVAL, JobStatus.TERMINATED},
    JobStatus.SENDING: {JobStatus.SENT, JobStatus.FAILED},
    JobStatus.SENT: set(),
    # Reprocess from scratch, or (after a send failure) go back for a fresh approval.
    JobStatus.FAILED: {JobStatus.QUEUED, JobStatus.AWAITING_APPROVAL, JobStatus.TERMINATED},
    JobStatus.TERMINATED: set(),
}


class InvalidTransition(Exception):
    pass


def transition(current: JobStatus, new: JobStatus) -> JobStatus:
    if new not in _ALLOWED[current]:
        raise InvalidTransition(f"{current.value} -> {new.value}")
    return new


def can_send(status: JobStatus) -> bool:
    """Sending is only legal for a job the user has explicitly approved."""
    return status == JobStatus.APPROVED
