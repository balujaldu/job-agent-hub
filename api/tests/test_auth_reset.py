"""Forgot password: set a new password and be signed in, without any verification."""
from fastapi.testclient import TestClient

from app.db import session_scope
from app.main import app
from app.models import Secret, User
from app.security import encrypt_json, hash_password

EMAIL = "reset-me@example.com"


def _register():
    """A client plus an account for EMAIL (created directly, since sign-up may be closed)."""
    with TestClient(app):
        pass  # runs startup so tables exist
    with session_scope() as db:
        if db.query(User).filter_by(email=EMAIL).one_or_none() is None:
            db.add(User(email=EMAIL, password_hash=hash_password("old-password-1")))
    return TestClient(app)


def test_reset_changes_password_and_signs_in():
    client = _register()
    r = client.post("/api/auth/reset-password", json={"email": EMAIL.upper(), "password": "brand-new-pass"})
    assert r.status_code == 200 and "session" in r.cookies
    assert client.get("/api/auth/me").json()["email"] == EMAIL

    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": "old-password-1"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": "brand-new-pass"}).status_code == 200


def test_reset_unknown_email_and_short_password():
    client = _register()
    assert client.post("/api/auth/reset-password", json={"email": "nobody@example.com", "password": "long-enough-1"}).status_code == 404
    assert client.post("/api/auth/reset-password", json={"email": EMAIL, "password": "short"}).status_code == 422


def test_reset_disconnects_gmail():
    client = _register()
    with session_scope() as db:
        uid = db.query(User).filter_by(email=EMAIL).one().id
        db.add(Secret(user_id=uid, kind="gmail", ciphertext=encrypt_json({"x": 1})))
    assert client.post("/api/auth/reset-password", json={"email": EMAIL, "password": "another-pass-2"}).status_code == 200
    with session_scope() as db:
        assert db.query(Secret).filter_by(user_id=uid).count() == 0
