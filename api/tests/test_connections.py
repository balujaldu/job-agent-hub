"""Connecting Gmail, Gmail expiry, and the sign-up switch."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from app import gmail
from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import Secret
from app.security import encrypt_json, sign

OWNER = {"email": "jane@example.com", "password": "correct-horse"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json=OWNER)
        if r.status_code in (403, 409):
            r = c.post("/api/auth/login", json=OWNER)
        assert r.status_code == 200, r.text
        yield c


def _uid(client) -> int:
    with session_scope() as s:
        from app.models import User
        return s.query(User).filter_by(email=OWNER["email"]).one().id


def test_second_signup_needs_allow_signups(client, monkeypatch):
    other = {"email": "sam@example.com", "password": "another-pass"}
    assert client.post("/api/auth/register", json=other).status_code == 403
    assert client.get("/api/auth/status").json()["signups_open"] is False

    monkeypatch.setattr(get_settings(), "allow_signups", True)
    assert client.get("/api/auth/status").json()["signups_open"] is True
    assert client.post("/api/auth/register", json=other).status_code == 200
    assert client.post("/api/auth/register", json=other).status_code == 409


def test_gmail_refresh_failure_disconnects(client, monkeypatch):
    uid = _uid(client)
    creds = {"client_id": "c", "client_secret": "s", "refresh_token": "r", "token": None}
    with session_scope() as db:
        db.query(Secret).filter_by(user_id=uid, kind="gmail").delete()
        db.add(Secret(user_id=uid, kind="gmail", label="jane@gmail.com", ciphertext=encrypt_json(json.dumps(creds))))

    def revoked(self, request):
        raise RefreshError("invalid_grant")

    monkeypatch.setattr(Credentials, "refresh", revoked)
    with session_scope() as db:
        with pytest.raises(gmail.GmailError, match="Reconnect Gmail"):
            gmail._credentials(db, uid)
        assert gmail.connected_address(db, uid) == ""


def test_gmail_connect_reads_address_from_id_token(client, monkeypatch):
    """Only gmail.send is granted, so the address must come from the ID token, not a Gmail read call."""
    uid = _uid(client)

    class FakeFlow:
        credentials = SimpleNamespace(id_token="signed.jwt", to_json=lambda: '{"token": "t"}')

        def fetch_token(self, code):
            assert code == "abc"

    monkeypatch.setattr(gmail, "_flow", lambda verifier=None: FakeFlow())
    monkeypatch.setattr(gmail.id_token, "verify_oauth2_token", lambda tok, req, aud: {"email": "jane@gmail.com"})
    monkeypatch.setattr(gmail, "build", lambda *a, **k: pytest.fail("no Gmail API call is allowed during connect"))
    state = sign({"uid": uid, "cv": None, "typ": "gmail"}, 15)
    r = client.get(f"/api/gmail/callback?state={state}&code=abc", follow_redirects=False)
    assert r.headers["location"].endswith("/settings?gmail=connected")
    assert client.get("/api/settings").json()["gmail"]["address"] == "jane@gmail.com"
