from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .models import AgentEvent

logger = logging.getLogger("agents")


def log_event(db: Session, job_id: int, agent: str, message: str, level: str = "info") -> None:
    db.add(AgentEvent(job_id=job_id, agent=agent, message=message, level=level))
    db.commit()
    logger.log(logging.WARNING if level != "info" else logging.INFO, "job %s [%s] %s", job_id, agent, message)
