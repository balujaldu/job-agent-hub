"""Files the app keeps: uploaded resumes, job screenshots and generated PDFs.

Local disk (under DATA_DIR) in development, a private Supabase Storage bucket online, where the
server's own disk is wiped on every deploy. The database stores keys like "uploads/resume-<uuid>.pdf",
never absolute paths, so rows work with either backend."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx

from .config import get_settings

# Tests swap in an httpx.MockTransport.
_transport: Optional[httpx.BaseTransport] = None


class StorageError(Exception):
    pass


def _local_path(key: str) -> Path:
    path = Path(key)
    return path if path.is_absolute() else get_settings().data_dir / key  # absolute: rows from before keys


def _client() -> httpx.Client:
    s = get_settings()
    key = s.supabase_service_role_key
    headers = {"apikey": key}
    if key.startswith("eyJ"):  # legacy service_role JWT; new sb_secret_ keys go in apikey only
        headers["Authorization"] = f"Bearer {key}"
    return httpx.Client(base_url=f"{s.supabase_url.rstrip('/')}/storage/v1/object/{s.supabase_bucket}/",
                        headers=headers, timeout=60, transport=_transport)


def _supabase() -> bool:
    return get_settings().storage_backend == "supabase"


def put(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    if _supabase():
        with _client() as http:
            r = http.post(key, content=data, headers={"Content-Type": content_type, "x-upsert": "true"})
        if r.status_code >= 300:
            raise StorageError(f"Couldn't save {key} to storage ({r.status_code}).")
    else:
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return key


def get(key: str) -> bytes:
    """Raises FileNotFoundError if the file doesn't exist."""
    if _supabase():
        with _client() as http:
            r = http.get(key)
        if r.status_code in (400, 404):  # Supabase answers 400 "not_found" for missing objects
            raise FileNotFoundError(key)
        if r.status_code >= 300:
            raise StorageError(f"Couldn't read {key} from storage ({r.status_code}).")
        return r.content
    return _local_path(key).read_bytes()


def delete(key: str) -> None:
    if _supabase():
        with _client() as http:
            http.delete(key)
    else:
        _local_path(key).unlink(missing_ok=True)
