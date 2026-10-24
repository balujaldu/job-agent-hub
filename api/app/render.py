"""Tailored resume -> ATS-safe plain text, HTML and PDF (single column, no tables)."""
from __future__ import annotations

from html import escape
from typing import List


def _dates(item: dict) -> str:
    return " – ".join(p for p in (item.get("start", ""), item.get("end", "")) if p)


def _contact(r: dict) -> List[str]:
    return [p for p in [r.get("email"), r.get("phone"), r.get("location"), *r.get("links", [])] if p]


def to_text(r: dict) -> str:
    lines = [r.get("name", ""), " · ".join(_contact(r)), ""]
    if r.get("summary"):
        lines += ["Summary", r["summary"], ""]
    lines += ["Skills", ", ".join(s["name"] for s in r.get("skills", [])), ""]
    lines.append("Experience")
    for e in r.get("experience", []):
        lines.append(f"{e['title']}, {e['company']} {_dates(e)}".strip())
        lines += [f"- {b['text']}" for b in e["bullets"]]
        lines.append("")
    if r.get("projects"):
        lines.append("Projects")
        for p in r["projects"]:
            lines.append(p["name"] + (f": {p['description']}" if p.get("description") else ""))
            lines += [f"- {b['text']}" for b in p["bullets"]]
        lines.append("")
    lines.append("Education")
    for ed in r.get("education", []):
        degree = ", ".join(x for x in (ed.get("degree"), ed.get("field")) if x)
        lines.append(f"{degree} {ed['institution']} {_dates(ed)}".strip())
    if r.get("certifications"):
        lines += ["", "Certifications", *r["certifications"]]
    return "\n".join(lines)


CSS = """
@page { size: Letter; margin: 0.55in 0.6in; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 10.5pt; line-height: 1.35; color: #111; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 2pt; }
.contact { font-size: 9.5pt; color: #333; margin-bottom: 8pt; }
h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid #999;
     margin: 10pt 0 4pt; padding-bottom: 2pt; }
.role { margin: 6pt 0 2pt; break-inside: avoid; }
.role-head { display: flex; justify-content: space-between; gap: 12pt; font-weight: bold; }
.role-head .dates { font-weight: normal; white-space: nowrap; }
ul { margin: 2pt 0 0 14pt; padding: 0; }
li { margin: 1pt 0; }
p { margin: 0; }
"""


def to_html(r: dict) -> str:
    h = escape
    parts = [f"<h1>{h(r.get('name', ''))}</h1>", f"<div class='contact'>{h(' · '.join(_contact(r)))}</div>"]
    if r.get("summary"):
        parts += ["<h2>Summary</h2>", f"<p>{h(r['summary'])}</p>"]
    parts += ["<h2>Skills</h2>", f"<p>{h(', '.join(s['name'] for s in r.get('skills', [])))}</p>"]
    parts.append("<h2>Experience</h2>")
    for e in r.get("experience", []):
        where = ", ".join(x for x in (e["company"], e.get("location", "")) if x)
        parts.append(
            f"<div class='role'><div class='role-head'><span>{h(e['title'])} — {h(where)}</span>"
            f"<span class='dates'>{h(_dates(e))}</span></div>"
            "<ul>" + "".join(f"<li>{h(b['text'])}</li>" for b in e["bullets"]) + "</ul></div>"
        )
    if r.get("projects"):
        parts.append("<h2>Projects</h2>")
        for p in r["projects"]:
            desc = f" — {h(p['description'])}" if p.get("description") else ""
            parts.append(
                f"<div class='role'><div class='role-head'><span>{h(p['name'])}{desc}</span></div>"
                "<ul>" + "".join(f"<li>{h(b['text'])}</li>" for b in p["bullets"]) + "</ul></div>"
            )
    parts.append("<h2>Education</h2>")
    for ed in r.get("education", []):
        degree = ", ".join(x for x in (ed.get("degree"), ed.get("field")) if x)
        parts.append(
            f"<div class='role'><div class='role-head'><span>{h(degree)}{' — ' if degree else ''}{h(ed['institution'])}</span>"
            f"<span class='dates'>{h(_dates(ed))}</span></div></div>"
        )
    if r.get("certifications"):
        parts += ["<h2>Certifications</h2>", "<ul>" + "".join(f"<li>{h(c)}</li>" for c in r["certifications"]) + "</ul>"]
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(parts)}</body></html>"


def to_pdf(r: dict) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(to_html(r), wait_until="load")
            return page.pdf(print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def pdf_key(job_id: int, name: str) -> str:
    slug = "-".join("".join(c for c in name.lower() if c.isalnum() or c == " ").split())[:40] or "candidate"
    return f"resumes/job-{job_id}-{slug}-resume.pdf"


def pdf_filename(key: str) -> str:
    """The name recipients see: "resumes/job-12-jane-doe-resume.pdf" -> "jane-doe-resume.pdf"."""
    return key.rsplit("/", 1)[-1].split("-", 2)[-1]
