# Job Agent Hub

Submit a job posting (screenshot or pasted text). AI agents then:
1. tailor your resume to the job,
2. score it for ATS keyword coverage,
3. find a hiring email on the company's site,
4. draft an application email.

**Nothing is sent until you click Approve.**

## How it works

| Agent | What it does |
|---|---|
| Extractor | Reads the screenshot or text and pulls out the company, role, job description, emails and ATS keywords. |
| ATS scorer | Scores keyword coverage and format, the same way for your base resume and the tailored one. |
| Resume tailor | Rewrites bullets and skills for the job. It may infer new points, but employers, titles, dates and education always come from your base resume, and every inferred item is highlighted for review. |
| PDF renderer | Produces a single-column, ATS-safe PDF. |
| Email finder | Uses an email from the posting if there is one. Otherwise it crawls the company's careers and contact pages (respecting robots.txt) and accepts only hiring addresses such as careers@ or jobs@. If none turn up, the job is marked **Email Not Found** and the drafts are still produced. |
| Composer | Writes the application email. |
| Gmail sender | Sends with the PDF attached, only for approved jobs. |

Job statuses: Queued → Processing → Awaiting approval / Email Not Found → Approved → Sending → Sent. A job can also end up Failed (retryable) or Terminated.

## Setup

### The AI model (Gemini, free)

The agents run on Google Gemini by default. Create a free API key at https://aistudio.google.com/apikey, put it in `api/.env` as `GEMINI_API_KEY=...` (not in `.env.example`), and restart the API. `GEMINI_MODEL` defaults to `gemini-3.5-flash`, which answered quickly on the free tier when tested (the newest Flash, reached through `gemini-flash-latest`, was timing out). Google retires models over time; if you get a "model wasn't found" error, pick a current Flash model from Google AI Studio.

- The free tier has per-minute and per-day limits. The app waits and retries briefly, then shows a clear message in the job's Activity feed.
- On the free tier, Google may use prompts and responses to improve its products. Those prompts contain resumes and job descriptions, so tell friends who use the app.
- To use Claude instead, set `LLM_PROVIDER=claude` and `ANTHROPIC_API_KEY` (a paid API key; a Claude subscription doesn't include one).
- Tailoring prompts were written for Claude. Check the first few tailored resumes; the code still forces employers, titles, dates and education to match the base resume whatever the model.

Requirements: Python 3.12 (via `uv`) and Node 22 (via `nvm`). Both are already installed on this machine.

```bash
cp api/.env.example api/.env      # then add GEMINI_API_KEY and SECRET_KEY
./dev.sh                          # API on :8000, web app on :3000
```

Open http://localhost:3000. Create your account, then upload your resume.

To set up from scratch on another machine:

```bash
cd api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/playwright install chromium
cd ../web && npm install
```

### Connecting Gmail

Users never enter API keys. After signing in they click **Connect Gmail** in Settings (or in the optional step after uploading their resume), sign in on Google's own page, allow sending, and are sent back to the app. Tokens are stored encrypted in `api/data`.

As the app owner you register the app with Google once and put its client ID and secret in `api/.env`:

**Gmail** (needed to send applications)
1. In Google Cloud Console, enable the Gmail API.
2. Create an OAuth client of type **Web application**.
3. Add `http://localhost:3000/api/gmail/callback` as an authorized redirect URI (add your production URL too when you deploy).
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, restart the API, and click **Connect Gmail**.

The app asks only for permission to send, not to read mail. While the consent screen is in "Testing" mode, only listed test users (up to 100) can connect, and Google expires their access after 7 days; the app then asks them to reconnect. To open the app to other people, submit it for Google's verification, which is required for the `gmail.send` scope.

### Passwords

**Forgot password?** on the sign-in page lets anyone enter an account's email and choose a new password, then signs them in. There is deliberately no email check, because the app is meant for a few friends. To limit the damage, a reset disconnects that account's Gmail, so it has to be connected again. Add email verification before putting the app in front of strangers.

### More than one user

By default only the first account can register. Set `ALLOW_SIGNUPS=true` in `api/.env` to let other people create accounts; each user connects their own Gmail.

## Deploying

| Part | Where | Why |
|---|---|---|
| Website (`web/`) | Vercel | Next.js host; proxies `/api/*` to the backend so cookies stay same-origin. |
| Backend (`api/`) | Render, free Docker web service (`render.yaml`) | Background agent jobs and the Chromium PDF renderer need a long-running server. |
| Database | Supabase Postgres | Render's disk is wiped on every deploy. |
| Files (resumes, screenshots, PDFs) | Supabase Storage, private bucket `app-files` | Same reason. |

1. **Supabase:** create a project. In Storage, create a **private** bucket named `app-files`. Note the project URL, the session-pooler connection string (Connect → Session pooler) and the secret / service-role key (Project Settings → API keys).
2. **Render:** New → Blueprint → select this repo. Fill in the values `render.yaml` asks for. Generate `SECRET_KEY` with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and `ENCRYPTION_KEY` with `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep both safe: changing `ENCRYPTION_KEY` disconnects everyone's Gmail. The API refuses to start if these are missing.
3. **Vercel:** import the repo, set Root Directory to `web`, and add `API_URL=https://<your-render-service>.onrender.com`. It's read at build time, so redeploy after changing it.
4. **Connect them:** set Render's `FRONTEND_URL` to the Vercel URL. In Google Cloud, add `https://<vercel-domain>/api/gmail/callback` as an authorized redirect URI.

Free-tier notes:
- **Render** sleeps after 15 idle minutes, so the first request afterwards takes about a minute.
- **Supabase** pauses projects after about a week without activity; restore them from the dashboard.
- **Jobs** run one at a time (`WORKER_THREADS=1`) to fit Render's 512 MB.

## Tests

```bash
cd api && .venv/bin/pytest -q          # backend, with the AI model, Gmail and the browser faked
cd web && npm run build && npm run lint
```

## Layout

```
api/app/agents/   extractor, tailor, composer, email_finder, resume_reader
api/app/pipeline.py   runs the agents for a job (never sends)
api/app/outbox.py     the only code that sends; re-checks approval before each send
api/app/state.py      job state machine
web/                  Next.js UI (jobs table + detail drawer, onboarding, settings)
```

Data (SQLite database, uploads, generated PDFs, encryption key) lives in `api/data/`, which is git-ignored.
