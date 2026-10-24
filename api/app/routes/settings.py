from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import gmail, outbox
from ..config import get_settings
from ..db import get_db
from ..deps import current_user
from ..models import User

router = APIRouter(prefix="/api", tags=["settings"])
logger = logging.getLogger(__name__)


@router.get("/settings")
def get_settings_view(user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = outbox.settings_for(db, user.id)
    cfg = get_settings()
    return {
        "sending_paused": s.sending_paused,
        "gmail": {"configured": cfg.gmail_configured, "address": gmail.connected_address(db, user.id),
                  "redirect_uri": cfg.gmail_redirect_uri},
        "model": cfg.llm_label,
    }


class SettingsUpdate(BaseModel):
    sending_paused: Optional[bool] = None


@router.put("/settings")
def update_settings(body: SettingsUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = outbox.settings_for(db, user.id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit()
    return get_settings_view(user, db)


# ---- Gmail -------------------------------------------------------------------

@router.get("/gmail/connect")
def gmail_connect(user: User = Depends(current_user)):
    try:
        return RedirectResponse(gmail.authorization_url(user.id))
    except gmail.GmailError as e:
        raise HTTPException(400, str(e))


@router.get("/gmail/callback")
def gmail_callback(state: str = "", code: str = "", error: str = "",
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    front = get_settings().frontend_url
    if error or not code:
        return RedirectResponse(f"{front}/settings?gmail=error&reason={error or 'cancelled'}")
    try:
        gmail.complete_authorization(db, user.id, state, code)
    except Exception as e:
        logger.exception("gmail connect failed for user %s", user.id)
        return RedirectResponse(f"{front}/settings?gmail=error&reason={type(e).__name__}")
    return RedirectResponse(f"{front}/settings?gmail=connected")


@router.post("/gmail/disconnect")
def gmail_disconnect(user: User = Depends(current_user), db: Session = Depends(get_db)):
    gmail.disconnect(db, user.id)
    return {"ok": True}
