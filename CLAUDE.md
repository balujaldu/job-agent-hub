# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Job Agent Hub is a single-user app. You submit a job posting (screenshot or pasted text), and AI agents (Gemini by default) tailor the base resume, score it for ATS, find a hiring email, and draft an application email. Nothing is sent until the user clicks Approve.

- `api/` holds the FastAPI backend and the agents (Python 3.12, SQLAlchemy, SQLite by default).
- `web/` holds the Next.js 15 frontend (React 19, Tailwind v4).

**The project folder name ends with a space (`product_1 `).** Always quote paths.

## Commands

```bash
./dev.sh                                   # API on :8000 (uvicorn --reload) + web on :3000 (next dev); needs api/.env

# Backend (run from api/)
.venv/bin/pytest -q                        # all tests; the AI model, Gmail and the browser are faked
.venv/bin/pytest -q tests/test_api.py::test_full_flow_sends_only_after_approval   # single test
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/playwright install chromium      # needed for PDF rendering

# Frontend (run from web/; Node comes from nvm: `. ~/.nvm/nvm.sh`)
npm run build                              # also type-checks and lints
npm run lint
```

- **Stopping servers:** stop them by port, e.g. `lsof -ti tcp:3000 | xargs kill`. Next renames its process to `next-server`, so `pkill -f "next start"` misses it and leaves a stale server serving old HTML against new chunks.
- **After editing `api/.env`:** restart the API. `uvicorn --reload` only watches `app/`, and `get_settings()` is cached, so a new key isn't picked up otherwise.
- **After renaming or moving the folder:** recreate `api/.venv`. Its scripts hard-code absolute paths.

## Architecture

**Request flow.** The browser only talks to Next on :3000. `web/next.config.ts` rewrites `/api/*` to FastAPI, so cookies are same-origin. Auth is a JWT in an httpOnly `session` cookie. Only the first account can register unless `ALLOW_SIGNUPS=true`; all data is already scoped by `user_id`. `POST /api/auth/reset-password` (the login page's "Forgot password?") sets a new password and signs in with no verification, by the owner's decision; it deletes that user's `gmail` secret so a reset can't be used to send as them. The UI polls; there is no SSE or websocket. The jobs list and the open drawer poll quickly while any job is in an active status.

**Job lifecycle.** `api/app/state.py` is the state machine and the source of truth: `queued → processing → awaiting_approval | email_not_found → approved → sending → sent`, plus `failed` (retryable) and `terminated`. All status changes go through `transition()`.

**Pipeline vs outbox, the core safety invariant:**
- **`api/app/pipeline.py` (`run_job`)** runs agents in order: extract, base ATS, tailor, render PDF, find recipient, compose. It logs each step as an `AgentEvent`, which the UI shows as the activity feed. It never sends. Between steps, `_checkpoint` re-reads the job so a user Terminate stops it. The final status write is a conditional UPDATE, so a late Terminate still wins.
- **`api/app/outbox.py`** is the only module that sends anything. `approve_email` records approval, guarded by the pause switch and the Gmail connection. `send_email` re-checks `can_send()` and the pause switch right before sending. Keep any new send path in this module.

**Background work.** `api/app/worker.py` runs an in-process `ThreadPoolExecutor`; there's no external queue. On startup, jobs stuck in `processing`/`sending` are marked failed, and `queued` jobs are resubmitted. Tests monkeypatch `worker.submit` to run work inline.

**Agents** (`api/app/agents/`) each make one structured model call through `api/app/llm.py`, which is provider-neutral:
- **Provider.** `LLM_PROVIDER` is `gemini` (default; `GEMINI_API_KEY`, `GEMINI_MODEL`, free tier) or `claude` (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`). The `.env` file is read through `Settings`; the SDKs don't read it themselves.
- **Neutral API.** Agents call `structured(system, content, schema, effort=…)`, `web_search_text(prompt)` and `image_block` / `document_block`, which return provider-neutral dicts (`{"type","media_type","data": bytes}`) that each provider converts. Keep new agent code on these helpers and never import an SDK in an agent.
- **Gemini path:** `generate_content` with `response_schema`, validated again with `model_validate_json`; 429/500/503 are retried (`_RETRY_DELAYS`), and every failure, block or truncation maps to `LLMError`, whose message is shown to the user. Web search is Google Search grounding.
- **Claude path:** `client.beta.messages.parse` with the server-side refusal fallback (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`); web search is `web_search_20260209` with `pause_turn` handling. `anthropic` is 2.x; check signatures against the installed SDK rather than memory.
- **Gemini model:** defaults to `gemini-3.5-flash`. The `gemini-flash-latest` alias was timing out (504) in Oct 2026, and Google retires older models (`gemini-2.5-flash` returns 404 for new keys), so check with `client.models.list()` before changing it.
- **Free-tier caveat:** `effort` is ignored by Gemini. Prompts were written for Claude, so verify output quality after changing models.

**Tailoring guardrails, enforced in code (`agents/tailor.py:assemble`).** The model only returns bullets, skills and summary, keyed by `base_index`. Employers, titles, dates, education and certifications are always copied from the base resume. Roles the model omits keep their original bullets. Skill provenance is recomputed: listed on the resume or in the user's confirmed `extra_skills` → `original`, otherwise `inferred`. Inferred items are highlighted in the UI. The `PUT /api/jobs/{id}/tailored` edit endpoint likewise restores structural fields from the stored version.

**ATS score (`api/app/ats.py`)** is deterministic: 70 points keyword coverage plus 30 points format checks. Keywords are extracted once per job by the extractor and stored on `Job.keywords`, so before and after scores use the same list. Before is scored on the base resume's raw text; after on `render.to_text(tailored)`.

**Email finder (`agents/email_finder.py`)** uses only the company's own site. It crawls the homepage, common careers/contact paths and links found on the homepage, and respects robots.txt. It scores addresses and accepts only hiring-type local parts (score ≥ 10); generic inboxes like info@ are reported as alternatives but never used. Web search is used only to find the company homepage when the extractor didn't provide one.

**Email composer (`agents/composer.py`).** The model returns `EmailParts` (subject, greeting, 2-3 paragraphs, sign-off) and `assemble()` builds the body in code: greeting, blank-line-separated paragraphs, sign-off, then the candidate's name only. Contact details are never sent to the model and are scrubbed from paragraphs; all-caps resume names are title-cased (`display_name`).

**Rendering (`api/app/render.py`)** turns the tailored dict into a single-column HTML page, then prints a PDF with Playwright Chromium. The same dict feeds `to_text` for ATS scoring.

**Gmail (`api/app/gmail.py`)** uses OAuth with the `gmail.send` scope. Because the Google flow generates a PKCE verifier, the verifier travels inside the signed `state`. Credentials are stored encrypted in `secrets` (kind `gmail`). The redirect URI is `{FRONTEND_URL}/api/gmail/callback`. Only `gmail.send` (plus `openid`/email) is granted, so never call Gmail read endpoints such as `users.getProfile`: they return 403. The connected address comes from the verified ID token. A `RefreshError` (revoked, or the 7-day expiry in Google's Testing mode) deletes the secret so the UI shows Connect again.

**OAuth pattern.** `GET /api/gmail/connect` redirects to Google with a signed `state` (`security.sign` with `uid` + `typ`, 15 minutes), and the callback checks both before storing, then redirects to `/settings?gmail=connected|error`. Users never supply keys; only the owner's client ID/secret live in `api/.env`.

**Data and config.**
- **`api/app/config.py`:** pydantic-settings reads `api/.env` (or real env vars online). `db_url` rewrites `postgres://` URLs to `postgresql+psycopg://`. `production_problems()` lists missing settings, and the app refuses to start if any are present; with `DATABASE_URL` set it requires `ENCRYPTION_KEY` and a real `SECRET_KEY`.
- **Files go through `api/app/storage.py`** (`put` / `get` / `delete` by key, e.g. `uploads/resume-<uuid>.pdf`, `resumes/job-12-…pdf`). `STORAGE_BACKEND=local` writes under `data_dir`; `supabase` uses a private Storage bucket via REST. DB columns (`file_path`, `source_image_path`, `resume_pdf_path`) hold keys; old absolute paths still resolve locally. Never write files to disk directly: Render's disk is wiped on deploy.
- **`api/data/` (git-ignored, local only):** the SQLite database, local storage files, and `encryption.key` (auto-generated unless `ENCRYPTION_KEY` is set).
- **Tables:** created with `create_all` at startup; there are no migrations, so schema changes need a fresh database or a manual ALTER.
- **Timestamps:** SQLite returns naive datetimes that are actually UTC. Serialize them with `models.iso()`; a bare `.isoformat()` makes the browser read them as local time.

**Frontend.**
- **Shell:** `components/AppShell.tsx` gates every signed-in page. No session → `/login`; no confirmed `BaseResume` → `/onboarding`: the first-run resume upload, followed by an optional "Connect Gmail" step that reuses `components/ConnectedAccounts.tsx` from Settings.
- **Main screen:** `app/page.tsx`, a jobs table with filters, plus `components/JobDrawer.tsx`, the detail drawer with tabs Overview / Email / Resume / Activity. The drawer's footer actions depend on job status, and every send needs an inline confirmation. Editable drafts use a `useDraft` hook so polling doesn't overwrite unsaved edits.
- **Shared code:** API types are in `lib/types.ts` and mirror the dicts built in `api/app/routes/jobs.py` (`_summary`, `_detail`).
- **Styling:** "liquid glass" design. Colors are CSS tokens in `app/globals.css`, exposed as Tailwind colors (`bg-surface`, `text-muted`, `from-accent to-accent-2`, …); use those instead of raw palette classes. Surfaces are translucent, so build panels from the `glass` / `glass-strong` utilities and `.card` / `.btn*` / `.input` classes.
- **Themes:** light by default, dark via `prefers-color-scheme`, and `data-theme="light|dark"` on `<html>` overrides both. `components/ThemeToggle.tsx` sets it and stores it in localStorage; `lib/theme.ts` holds the inline boot script that `app/layout.tsx` puts in `<head>` to avoid a flash. Keep the dark token block duplicated under both the media query and `[data-theme="dark"]`.
- **Animations:** use `animation-fill-mode: backwards` (as `.animate-*` do), never `both`/`forwards` with transforms. A retained transform makes the element a containing block and traps `position: fixed` children such as the job drawer.

## Deployment

The website goes on Vercel (root `web/`, env `API_URL` read at build time by the rewrite). The backend goes on Render via `render.yaml` and `api/Dockerfile` (a Playwright base image whose version must match `playwright` in `requirements.txt`). Data lives in Supabase: Postgres through the session pooler, files in the private bucket `app-files`. Run a single backend instance, because jobs run in the in-process worker. Online config is env vars only, and secrets are `sync: false` in `render.yaml`.

## Tests

`api/tests/conftest.py` points `DATA_DIR` at a temp directory before any app import; the engine and settings are created at import time. `test_api.py` monkeypatches the agent functions on their modules, plus `render.to_pdf`, `gmail.send` and `gmail.connected_address`. It asserts the send log stays empty until approval. Follow the same pattern for new flows.
