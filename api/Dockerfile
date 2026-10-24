# Backend image for Render. The Playwright base image ships Chromium (used for the resume PDFs)
# and must match the playwright version pinned in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/tmp/data

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app

EXPOSE 8000
# One process: background jobs run in an in-process thread pool (app/worker.py).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
