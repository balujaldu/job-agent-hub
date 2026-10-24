"""Storage backends, Postgres URL handling and the production settings guard."""
import httpx
import pytest

from app import storage
from app.config import Settings, get_settings
from app.render import pdf_filename, pdf_key


def test_local_put_get_delete():
    key = storage.put("uploads/test-file.txt", b"hello", "text/plain")
    assert storage.get(key) == b"hello"
    assert (get_settings().data_dir / key).exists()
    storage.delete(key)
    with pytest.raises(FileNotFoundError):
        storage.get(key)


def test_local_reads_legacy_absolute_paths(tmp_path):
    legacy = tmp_path / "old.pdf"
    legacy.write_bytes(b"%PDF")
    assert storage.get(str(legacy)) == b"%PDF"


@pytest.fixture
def supabase(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "storage_backend", "supabase")
    monkeypatch.setattr(cfg, "supabase_url", "https://proj.supabase.co/")
    monkeypatch.setattr(cfg, "supabase_bucket", "app-files")
    objects, seen = {}, []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        prefix = "/storage/v1/object/app-files/"
        assert request.url.path.startswith(prefix)
        key = request.url.path[len(prefix):]
        if request.method == "POST":
            objects[key] = request.content
            return httpx.Response(200, json={"Key": key})
        if request.method == "GET":
            return httpx.Response(200, content=objects[key]) if key in objects else httpx.Response(400, json={"error": "not_found"})
        objects.pop(key, None)
        return httpx.Response(200, json={})

    monkeypatch.setattr(storage, "_transport", httpx.MockTransport(handler))
    return seen


def test_supabase_round_trip_with_new_secret_key(supabase, monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_service_role_key", "sb_secret_abc")
    storage.put("resumes/job-1-jane-resume.pdf", b"%PDF-data", "application/pdf")
    assert storage.get("resumes/job-1-jane-resume.pdf") == b"%PDF-data"
    first = supabase[0]
    assert first.headers["apikey"] == "sb_secret_abc" and "authorization" not in first.headers
    assert first.headers["x-upsert"] == "true" and first.headers["content-type"] == "application/pdf"
    storage.delete("resumes/job-1-jane-resume.pdf")
    with pytest.raises(FileNotFoundError):
        storage.get("resumes/job-1-jane-resume.pdf")


def test_supabase_legacy_jwt_key_also_sent_as_bearer(supabase, monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_service_role_key", "eyJhbGciOi.legacy")
    storage.put("uploads/x.png", b"img", "image/png")
    assert supabase[0].headers["authorization"] == "Bearer eyJhbGciOi.legacy"


def test_supabase_errors_raise(supabase, monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_service_role_key", "sb_secret_abc")
    monkeypatch.setattr(storage, "_transport", httpx.MockTransport(lambda r: httpx.Response(403, json={})))
    with pytest.raises(storage.StorageError, match="403"):
        storage.put("uploads/x.png", b"img")


@pytest.mark.parametrize("given, expected", [
    ("", None),
    ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
])
def test_database_url_uses_psycopg(given, expected):
    url = Settings(database_url=given).db_url
    assert url.startswith("sqlite:///") if expected is None else url == expected


def test_production_guard():
    assert Settings().production_problems() == []  # local development
    online = Settings(database_url="postgres://x", secret_key="dev-insecure-change-me", encryption_key="")
    problems = " ".join(online.production_problems())
    assert "ENCRYPTION_KEY" in problems and "SECRET_KEY" in problems
    ok = Settings(database_url="postgres://x", secret_key="long-random", encryption_key="k",
                  storage_backend="supabase", supabase_url="https://p.supabase.co", supabase_service_role_key="s")
    assert ok.production_problems() == []
    assert "SUPABASE_URL" in " ".join(Settings(storage_backend="supabase").production_problems())


def test_pdf_names():
    key = pdf_key(12, "Jaldu Balasubramanyam Guptha")
    assert key == "resumes/job-12-jaldu-balasubramanyam-guptha-resume.pdf"
    assert pdf_filename(key) == "jaldu-balasubramanyam-guptha-resume.pdf"
