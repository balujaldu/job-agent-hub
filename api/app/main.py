from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import worker
from .config import get_settings
from .db import init_db
from .routes import auth, jobs, resume, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    problems = get_settings().production_problems()
    if problems:
        raise RuntimeError("Fix these settings before starting:\n- " + "\n- ".join(problems))
    init_db()
    worker.recover_on_startup()
    yield
    worker.shutdown()


app = FastAPI(title="Job Agent Hub", lifespan=lifespan)
for r in (auth.router, resume.router, jobs.router, settings.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}
