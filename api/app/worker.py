"""In-process background worker. One user, a handful of jobs: a thread pool is enough."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from .config import get_settings
from .db import session_scope
from .events import log_event
from .models import Job
from .state import JobStatus

_executor: Optional[ThreadPoolExecutor] = None


def executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=get_settings().worker_threads, thread_name_prefix="agent")
    return _executor


def submit(fn: Callable, *args) -> None:
    executor().submit(fn, *args)


def recover_on_startup() -> None:
    """Jobs interrupted by a restart are marked failed (retryable); queued ones resume."""
    from .pipeline import run_job

    with session_scope() as db:
        for job in db.query(Job).filter(Job.status.in_([JobStatus.PROCESSING, JobStatus.SENDING])).all():
            was_sending = job.status == JobStatus.SENDING
            job.status = JobStatus.FAILED
            job.error = ("Interrupted while sending; check Gmail's Sent folder before retrying."
                         if was_sending else "Interrupted by a server restart.")
            log_event(db, job.id, "pipeline", job.error, "warn")
        queued = [j.id for j in db.query(Job).filter(Job.status == JobStatus.QUEUED).all()]
    for job_id in queued:
        submit(run_job, job_id)


def shutdown() -> None:
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
