from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", extra="ignore")

    data_dir: Path = API_DIR / "data"
    database_url: str = ""  # empty -> SQLite file in data_dir; online: Supabase Postgres (session pooler)

    # Where uploads and generated PDFs live: "local" (data_dir) or "supabase" (private Storage bucket).
    storage_backend: str = "local"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket: str = "app-files"

    # Signs session cookies and OAuth state. Must be set in production.
    secret_key: str = "dev-insecure-change-me"
    # Fernet key for stored OAuth tokens. Generated into data_dir if empty.
    encryption_key: str = ""

    frontend_url: str = "http://localhost:3000"
    cookie_secure: bool = False

    # Which model backs the agents: "gemini" (free API key from aistudio.google.com) or "claude".
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"  # fast on the free tier; "gemini-flash-latest" was timing out (Oct 2026)

    claude_model: str = "claude-opus-5-5"
    anthropic_api_key: str = ""  # empty -> SDK falls back to the environment / `ant auth login`

    google_client_id: str = ""
    google_client_secret: str = ""

    worker_threads: int = 2

    # Off: only the first account can register. Turn on to open sign-up to other people.
    allow_signups: bool = False

    @property
    def db_url(self) -> str:
        url = self.database_url
        if not url:
            return f"sqlite:///{self.data_dir / 'app.db'}"
        # Supabase and Render hand out postgres:// or postgresql:// URLs; use the installed psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    def production_problems(self) -> list[str]:
        """Settings that would lose data or weaken security online. Empty in local development."""
        problems = []
        if self.database_url:
            if "@db." in self.database_url and ".supabase.co" in self.database_url:
                problems.append("DATABASE_URL uses Supabase's direct connection, which is IPv6-only and unreachable from "
                                "Render. Use the Session pooler string (Connect -> Session pooler, host *.pooler.supabase.com).")
            if not self.encryption_key:
                problems.append("ENCRYPTION_KEY must be set, or stored Gmail connections become unreadable after a redeploy.")
            if self.secret_key == "dev-insecure-change-me":
                problems.append("SECRET_KEY must be set to a long random value.")
        if self.storage_backend == "supabase" and not (self.supabase_url and self.supabase_service_role_key):
            problems.append("STORAGE_BACKEND=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        if self.storage_backend not in ("local", "supabase"):
            problems.append("STORAGE_BACKEND must be 'local' or 'supabase'.")
        return problems

    @property
    def llm_label(self) -> str:
        model = self.claude_model if self.llm_provider == "claude" else self.gemini_model
        return f"{self.llm_provider} · {model}"

    @property
    def gmail_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def gmail_redirect_uri(self) -> str:
        return f"{self.frontend_url}/api/gmail/callback"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    for sub in ("", "uploads", "resumes"):
        (s.data_dir / sub).mkdir(parents=True, exist_ok=True)
    return s
