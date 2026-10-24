"""Deterministic ATS scoring: JD keyword coverage plus resume format checks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

KEYWORD_WEIGHT = 70
FORMAT_WEIGHT = 30
REQUIRED_SECTIONS = ("experience", "education", "skills")

_STOPWORDS = {
    "the", "and", "for", "with", "you", "our", "are", "will", "have", "has", "that",
    "this", "from", "your", "who", "all", "any", "can", "etc", "their", "such",
    "about", "into", "more", "other", "work", "team", "role", "job", "years",
    "experience", "ability", "strong", "good", "must", "should", "using", "use",
    "we", "an", "be", "to", "of", "in", "on", "or", "as", "is", "it", "at", "by",
    "need", "needs", "looking", "join", "plus", "new", "what", "within", "across",
    "including", "based", "well", "help", "like", "also", "per", "daily", "able",
}
_TOKEN = re.compile(r"[a-z][a-z0-9+#.\-]{1,}")


@dataclass
class ATSResult:
    score: int
    keyword_score: int
    format_score: int
    matched: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    format_issues: List[str] = field(default_factory=list)


def _norm(token: str) -> str:
    return token.strip(".-").lower()


def extract_keywords(jd_text: str, limit: int = 40) -> List[str]:
    """Most frequent non-stopword terms in the JD, in first-seen order on ties."""
    counts: dict = {}
    for raw in _TOKEN.findall(jd_text.lower()):
        tok = _norm(raw)
        if len(tok) < 2 or tok in _STOPWORDS:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts, key=lambda t: -counts[t])  # stable: keeps first-seen order
    return ranked[:limit]


def _format_checks(resume_text: str):
    issues: List[str] = []
    lowered = resume_text.lower()
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^\s*{section}\b", lowered, re.M):
            issues.append(f"missing section: {section}")
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume_text):
        issues.append("no email address")
    if "|" in resume_text or "\t" in resume_text:
        issues.append("table-like characters may break ATS parsing")
    if len(resume_text.split()) < 150:
        issues.append("resume is very short")
    return issues


def _flatten(text: str) -> str:
    """Lowercase, with punctuation that isn't part of tech names turned into spaces."""
    return " " + re.sub(r"[^a-z0-9+#.\-]+", " ", text.lower()) + " "


def _contains(flat_text: str, phrase: str) -> bool:
    words = [w for w in (_norm(w) for w in _flatten(phrase).split()) if w]
    if not words:
        return False
    pattern = r"(?<![a-z0-9+#])" + r"[\s.\-]+".join(re.escape(w) for w in words) + r"(?![a-z0-9+#])"
    return re.search(pattern, flat_text) is not None


def score_resume(resume_text: str, jd_text: str, keywords: Optional[List[str]] = None) -> ATSResult:
    """Score against `keywords` when given (phrases pulled from the JD once per job, so
    before/after scores use the same list), otherwise against frequency-ranked JD terms."""
    if keywords:
        keywords = list(dict.fromkeys(k.strip().lower() for k in keywords if k.strip()))
    else:
        keywords = extract_keywords(jd_text)
    flat = _flatten(resume_text)
    matched = [k for k in keywords if _contains(flat, k)]
    missing = [k for k in keywords if k not in matched]
    keyword_score = round(KEYWORD_WEIGHT * len(matched) / len(keywords)) if keywords else 0

    issues = _format_checks(resume_text)
    per_issue = FORMAT_WEIGHT / (len(REQUIRED_SECTIONS) + 3)
    format_score = max(0, round(FORMAT_WEIGHT - per_issue * len(issues)))

    return ATSResult(
        score=keyword_score + format_score,
        keyword_score=keyword_score,
        format_score=format_score,
        matched=matched,
        missing=missing,
        format_issues=issues,
    )
