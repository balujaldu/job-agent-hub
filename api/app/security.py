from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet

from .config import get_settings

SESSION_COOKIE = "session"
SESSION_DAYS = 14


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def sign(payload: dict, minutes: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({**payload, "exp": exp}, get_settings().secret_key, algorithm="HS256")


def unsign(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def session_token(user_id: int) -> str:
    return sign({"sub": str(user_id), "typ": "session"}, SESSION_DAYS * 24 * 60)


def _fernet() -> Fernet:
    s = get_settings()
    key = s.encryption_key
    if not key:
        key_file = s.data_dir / "encryption.key"
        if not key_file.exists():
            key_file.write_text(Fernet.generate_key().decode())
            key_file.chmod(0o600)
        key = key_file.read_text().strip()
    return Fernet(key.encode())


def encrypt_json(data: Any) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_json(token: str) -> Any:
    return json.loads(_fernet().decrypt(token.encode()))
