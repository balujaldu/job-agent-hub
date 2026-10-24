"""Drafts the application email.

The model writes the parts (subject, greeting, paragraphs, sign-off); the layout and the
signature are assembled here, so every email has the same readable structure and is signed
with the candidate's name only, never a phone number, address or link."""
from __future__ import annotations

import json
import re

from ..llm import structured
from ..schemas import Drafts, EmailParts

SYSTEM = """You write job-application emails for a candidate. Sound like a capable professional writing personally: specific, confident, brief. No clichés ("I hope this finds you well", "I am writing to express my interest"), no flattery, no exclamation marks, no emojis, no markdown.

subject: tailored to this role and company, e.g. "Application for Backend Engineer at Acme" or "Backend Engineer Role at Acme - Python and API Experience". Under 80 characters. Don't include the candidate's name.
greeting: "Dear <recruiter name>" if a recruiter is named, otherwise "Dear <company> Hiring Team".
paragraphs: 2 or 3 short paragraphs, 80-130 words in total:
  1. Which role you're applying for and one line on who the candidate is.
  2. The two or three most relevant skills or experiences for THIS job, with one concrete result from the resume.
  3. The resume is attached, and a simple invitation to talk.
sign_off: "Best regards".
Never include phone numbers, email addresses, links or the candidate's name in the paragraphs; the signature is added separately."""

_CONTACT = re.compile(
    r"https?://\S+|www\.\S+|[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{7,}\d"  # links, emails, phone numbers
)


def display_name(name: str) -> str:
    """Resumes often set the name in capitals; sign as "Jaldu Balasubramanyam Guptha", not all caps."""
    name = " ".join((name or "").split())
    return name.title() if name.isupper() else name


def _clean(text: str) -> str:
    text = _CONTACT.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def assemble(parts: EmailParts, name: str) -> Drafts:
    greeting = parts.greeting.strip().rstrip(",") or "Dear Hiring Team"
    paragraphs = [p for p in (_clean(p) for p in parts.paragraphs) if p][:3]
    sign_off = parts.sign_off.strip().rstrip(",") or "Best regards"
    body = f"{greeting},\n\n" + "\n\n".join(paragraphs) + f"\n\n{sign_off},\n{name}"
    subject = " ".join(parts.subject.split()).rstrip(".")[:90]
    return Drafts(email_subject=subject, email_body=body)


def compose(job: dict, tailored: dict) -> Drafts:
    name = display_name(tailored.get("name", ""))
    candidate = {
        "name": name,
        "summary": tailored.get("summary"),
        "top_skills": [s["name"] for s in tailored.get("skills", [])[:12]],
        "recent_roles": [
            {"company": e["company"], "title": e["title"], "highlights": [b["text"] for b in e["bullets"][:3]]}
            for e in tailored.get("experience", [])[:2]
        ],
    }
    prompt = (
        f"<job>\n{json.dumps(job, indent=1)}\n</job>\n\n"
        f"<candidate>\n{json.dumps(candidate, indent=1)}\n</candidate>"
    )
    parts = structured(SYSTEM, [{"type": "text", "text": prompt}], EmailParts, effort="medium")
    return assemble(parts, name)
