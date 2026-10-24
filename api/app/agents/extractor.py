"""Pulls company, role, JD text, emails and ATS keywords out of a screenshot or pasted text."""
from __future__ import annotations

import re
from typing import Optional

from ..llm import image_block, structured
from ..schemas import JobExtraction

SYSTEM = (
    "You read job postings, including screenshots of LinkedIn posts, careers pages and emails. "
    "Transcribe the job description faithfully. List every email address that is visible, "
    "exactly as written. For company_website, give the company's official homepage URL if it "
    "appears in the input or you are confident of it; otherwise leave it empty. Never guess "
    "email addresses."
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def extract_job(text: str = "", image: Optional[bytes] = None, media_type: str = "image/png") -> JobExtraction:
    content = []
    if image:
        content.append(image_block(image, media_type))
    if text:
        content.append({"type": "text", "text": f"Job posting text:\n\n{text}"})
    content.append({"type": "text", "text": "Extract the job details."})
    result = structured(SYSTEM, content, JobExtraction, effort="low")

    # Trust only addresses that literally appear in pasted text; a screenshot has no
    # text to check against, so the model's reading is used as is.
    emails = [e.strip().lower() for e in result.emails if _EMAIL.fullmatch(e.strip())]
    if text and not image:
        present = {e.lower() for e in _EMAIL.findall(text)}
        emails = [e for e in emails if e in present]
    result.emails = list(dict.fromkeys(emails))
    return result
