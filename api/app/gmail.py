"""Gmail OAuth and sending. Credentials are stored encrypted in the secrets table."""
from __future__ import annotations

import base64
import json
from email.message import EmailMessage
from typing import Optional, Tuple

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Secret
from .security import decrypt_json, encrypt_json, sign, unsign

SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/gmail.send"]


class GmailError(Exception):
    pass


def _flow(code_verifier: Optional[str] = None) -> Flow:
    s = get_settings()
    if not s.gmail_configured:
        raise GmailError("Gmail isn't configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in api/.env.")
    config = {"web": {
        "client_id": s.google_client_id,
        "client_secret": s.google_client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [s.gmail_redirect_uri],
    }}
    flow = Flow.from_client_config(config, scopes=SCOPES, redirect_uri=s.gmail_redirect_uri)
    if code_verifier:
        flow.code_verifier = code_verifier
    return flow


def authorization_url(user_id: int) -> str:
    flow = _flow()
    url, _ = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true",
        state=sign({"uid": user_id, "cv": flow.code_verifier, "typ": "gmail"}, 15),
    )
    return url


def complete_authorization(db: Session, user_id: int, state: str, code: str) -> str:
    payload = unsign(state)
    if not payload or payload.get("typ") != "gmail" or payload.get("uid") != user_id:
        raise GmailError("The Gmail sign-in link expired or doesn't match this account. Try again.")
    flow = _flow(payload["cv"])
    flow.fetch_token(code=code)
    creds = flow.credentials
    # The address comes from the signed ID token: users.getProfile needs a read scope, and we only ask to send.
    claims = id_token.verify_oauth2_token(creds.id_token, Request(), get_settings().google_client_id)
    address = claims["email"]
    secret = db.query(Secret).filter_by(user_id=user_id, kind="gmail").one_or_none() or Secret(user_id=user_id, kind="gmail")
    secret.label = address
    secret.ciphertext = encrypt_json(creds.to_json())
    db.add(secret)
    db.commit()
    return address


def connected_address(db: Session, user_id: int) -> str:
    secret = db.query(Secret).filter_by(user_id=user_id, kind="gmail").one_or_none()
    return secret.label if secret else ""


def disconnect(db: Session, user_id: int) -> None:
    db.query(Secret).filter_by(user_id=user_id, kind="gmail").delete()
    db.commit()


def _credentials(db: Session, user_id: int) -> Tuple[Credentials, str]:
    secret = db.query(Secret).filter_by(user_id=user_id, kind="gmail").one_or_none()
    if not secret:
        raise GmailError("Gmail isn't connected. Connect it in Settings.")
    creds = Credentials.from_authorized_user_info(json.loads(decrypt_json(secret.ciphertext)), SCOPES)
    if not creds.valid and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            # Revoked by the user, or Google's 7-day expiry for apps in Testing mode.
            db.delete(secret)
            db.commit()
            raise GmailError("Gmail access expired or was revoked. Reconnect Gmail in Settings.") from e
        secret.ciphertext = encrypt_json(creds.to_json())
        db.commit()
    return creds, secret.label


def build_message(sender: str, to: str, subject: str, body: str,
                  attachment: Optional[Tuple[str, bytes]]) -> EmailMessage:
    """attachment is (filename, PDF bytes)."""
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg.set_content(body)
    if attachment:
        filename, data = attachment
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=filename)
    return msg


def send(db: Session, user_id: int, to: str, subject: str, body: str, attachment: Optional[Tuple[str, bytes]]) -> str:
    """Sends one email and returns the Gmail message id. Callers must have checked approval."""
    creds, sender = _credentials(db, user_id)
    raw = base64.urlsafe_b64encode(build_message(sender, to, subject, body, attachment).as_bytes()).decode()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]
