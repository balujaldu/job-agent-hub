"""Tailors the base resume to a JD. The model only rewrites bullets, skills and the summary;
employers, titles, dates, education and certifications always come from the base resume."""
from __future__ import annotations

import json
from typing import List

from ..llm import structured
from ..schemas import ResumeData, TailorOutput

MAX_BULLETS = 8

SYSTEM = """You tailor resumes to job descriptions so they pass ATS screening and read well to a recruiter.

The candidate has confirmed they can handle every skill they list and the work implied by their past roles. You may:
- reword and reorder existing bullets to use the job description's language (provenance "reworded"; unchanged bullets are "original"),
- add bullets describing responsibilities that the role and company plausibly involved, aligned with the job description (provenance "inferred"),
- add skills the job asks for that fit the candidate's background (provenance "inferred").

You must not:
- change employers, job titles, dates, degrees or schools. Refer to experience entries only by base_index,
- invent specific numbers, percentages, revenue figures or team sizes that are not in the base resume,
- write anything that would contradict the base resume.

Work the missing keywords in naturally where they fit. Keep 3-6 bullets per role, most relevant first, each one line starting with a strong verb. Summary: 2-3 sentences aimed at this role. Include every experience entry from the base resume."""


def tailor(base: ResumeData, extra_skills: List[str], extra_notes: str, jd_text: str,
           keywords: List[str], missing: List[str]) -> TailorOutput:
    indexed = {
        "summary": base.summary,
        "skills": base.skills,
        "experience": [
            {"base_index": i, "company": e.company, "title": e.title, "dates": f"{e.start} - {e.end}", "bullets": e.bullets}
            for i, e in enumerate(base.experience)
        ],
        "projects": [
            {"base_index": i, "name": p.name, "description": p.description, "bullets": p.bullets}
            for i, p in enumerate(base.projects)
        ],
    }
    prompt = (
        f"<base_resume>\n{json.dumps(indexed, indent=1)}\n</base_resume>\n\n"
        f"<confirmed_extra_skills>\n{', '.join(extra_skills) or '(none)'}\n</confirmed_extra_skills>\n\n"
        f"<candidate_notes>\n{extra_notes or '(none)'}\n</candidate_notes>\n\n"
        f"<job_description>\n{jd_text}\n</job_description>\n\n"
        f"<ats_keywords>{', '.join(keywords)}</ats_keywords>\n"
        f"<missing_keywords>{', '.join(missing) or '(none)'}</missing_keywords>"
    )
    return structured(SYSTEM, [{"type": "text", "text": prompt}], TailorOutput, effort="high", max_tokens=32000)


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def assemble(base: ResumeData, out: TailorOutput, extra_skills: List[str]) -> dict:
    """Merge model output onto the base resume, enforcing the guardrails in code."""
    base_bullets = {_norm(b) for e in base.experience for b in e.bullets} | {
        _norm(b) for p in base.projects for b in p.bullets
    }

    def clean_bullets(items) -> List[dict]:
        result, seen = [], set()
        for b in items:
            text = " ".join(b.text.split())
            if not text or _norm(text) in seen:
                continue
            seen.add(_norm(text))
            prov = "original" if _norm(text) in base_bullets else b.provenance
            if prov == "original" and _norm(text) not in base_bullets:
                prov = "reworded"
            result.append({"text": text, "provenance": prov})
        return result[:MAX_BULLETS]

    by_exp = {t.base_index: t for t in out.experience if 0 <= t.base_index < len(base.experience)}
    experience = []
    for i, e in enumerate(base.experience):
        bullets = clean_bullets(by_exp[i].bullets) if i in by_exp else []
        if not bullets:  # never drop a role: fall back to the original bullets
            bullets = [{"text": b, "provenance": "original"} for b in e.bullets]
        experience.append({**e.model_dump(exclude={"bullets"}), "bullets": bullets})

    by_proj = {t.base_index: t for t in out.projects if 0 <= t.base_index < len(base.projects)}
    projects = []
    for i, p in enumerate(base.projects):
        bullets = clean_bullets(by_proj[i].bullets) if i in by_proj else []
        if not bullets:
            bullets = [{"text": b, "provenance": "original"} for b in p.bullets]
        projects.append({**p.model_dump(exclude={"bullets"}), "bullets": bullets})

    # Skill provenance is recomputed: listed on the resume or confirmed by the user -> original.
    known = {_norm(s) for s in base.skills} | {_norm(s) for s in extra_skills}
    skills, seen = [], set()
    for s in out.skills:
        name = s.name.strip()
        if not name or _norm(name) in seen:
            continue
        seen.add(_norm(name))
        skills.append({"name": name, "provenance": "original" if _norm(name) in known else "inferred"})

    return {
        "name": base.name,
        "email": base.email,
        "phone": base.phone,
        "location": base.location,
        "links": base.links,
        "summary": out.summary.strip() or base.summary,
        "skills": skills or [{"name": s, "provenance": "original"} for s in base.skills],
        "experience": experience,
        "projects": projects,
        "education": [e.model_dump() for e in base.education],
        "certifications": base.certifications,
    }
