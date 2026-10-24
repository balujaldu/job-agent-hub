"""Finds a hiring email on the company's own careers, jobs and contact pages.

Only addresses published on the company's site count. Hiring-specific addresses
(careers@, jobs@, hr@, recruiting@ ...) are accepted; general inboxes such as info@
are reported as alternatives but not used automatically."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from ..llm import web_search_text

USER_AGENT = "Mozilla/5.0 (compatible; JobAgentHub/1.0; careers-contact lookup)"
MAX_PAGES = 12
HIRING_THRESHOLD = 10

PAGE_HINTS = ("career", "jobs", "job", "join", "hiring", "recruit", "talent", "work-with-us",
              "contact", "about", "people", "team")
COMMON_PATHS = ("/careers", "/jobs", "/join-us", "/contact", "/contact-us", "/about")

HIRING_LOCAL = ("career", "job", "hr", "recruit", "talent", "hiring", "hire", "people", "join", "resume", "cv", "apply")
GENERAL_LOCAL = ("info", "contact", "hello", "hi", "office", "admin", "team")
BAD_LOCAL = ("noreply", "no-reply", "donotreply", "privacy", "legal", "abuse", "press", "media", "sales",
             "support", "billing", "security", "gdpr", "dpo", "unsubscribe", "webmaster", "postmaster",
             "invoice", "accounts", "marketing", "partners")
BAD_DOMAINS = ("example.com", "sentry.io", "wixpress.com", "domain.com", "email.com", "yourcompany.com")

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_OBFUSCATED = [
    (re.compile(r"\s*[\[(\{]\s*at\s*[\])\}]\s*", re.I), "@"),
    (re.compile(r"\s*[\[(\{]\s*dot\s*[\])\}]\s*", re.I), "."),
]
_FILE_SUFFIX = re.compile(r"\.(png|jpe?g|gif|svg|webp|css|js)$", re.I)


@dataclass
class Candidate:
    email: str
    score: int
    page: str


@dataclass
class FinderResult:
    email: str = ""
    source: str = ""
    alternatives: List[Candidate] = field(default_factory=list)
    pages_checked: List[str] = field(default_factory=list)
    website: str = ""
    note: str = ""


def _root_domain(host: str) -> str:
    parts = host.lower().split(".")
    if parts[0] == "www":
        parts = parts[1:]
    # good enough for example.co.uk style suffixes
    if len(parts) > 2 and len(parts[-1]) == 2 and parts[-2] in ("co", "com", "org", "net", "ac", "gov"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def normalize_url(url: str) -> str:
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def find_emails_in_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for a in soup.select('a[href^="mailto:"]'):
        found.append(a["href"][7:].split("?")[0])
    text = soup.get_text(" ")
    for pattern, repl in _OBFUSCATED:
        text = pattern.sub(repl, text)
    found.extend(_EMAIL.findall(text))
    out = []
    for e in found:
        e = e.strip().strip(".").lower()
        if _EMAIL.fullmatch(e) and not _FILE_SUFFIX.search(e):
            out.append(e)
    return list(dict.fromkeys(out))


def score_email(email: str, company_domain: str, page_url: str) -> int:
    local, _, domain = email.partition("@")
    if any(domain.endswith(d) for d in BAD_DOMAINS) or any(b in local for b in BAD_LOCAL):
        return -100
    score = 0
    if any(h in local for h in HIRING_LOCAL):
        score += 10
    elif any(local.startswith(g) for g in GENERAL_LOCAL):
        score += 3
    if company_domain and _root_domain(domain) == company_domain:
        score += 5
    elif company_domain:
        score -= 4  # third-party address on the company's page
    if any(h in page_url.lower() for h in ("career", "job", "join", "hiring", "recruit")):
        score += 3
    return score


def _candidate_links(html: str, base_url: str, company_domain: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url + "/", a["href"]).split("#")[0]
        host = urlparse(href).hostname or ""
        if not href.startswith("http") or _root_domain(host) != company_domain:
            continue
        label = (a.get_text(" ") + " " + href).lower()
        if any(h in label for h in PAGE_HINTS):
            links.append(href.rstrip("/"))
    return list(dict.fromkeys(links))


class _Robots:
    def __init__(self, http: httpx.Client, base_url: str):
        self.parser: Optional[RobotFileParser] = None
        try:
            r = http.get(base_url + "/robots.txt")
            if r.status_code == 200:
                self.parser = RobotFileParser()
                self.parser.parse(r.text.splitlines())
        except httpx.HTTPError:
            pass

    def allowed(self, url: str) -> bool:
        return self.parser is None or self.parser.can_fetch(USER_AGENT, url)


def crawl_for_email(website: str, http: Optional[httpx.Client] = None,
                    log: Callable[[str], None] = lambda m: None) -> FinderResult:
    base = normalize_url(website)
    result = FinderResult(website=base)
    host = urlparse(base).hostname
    if not host:
        result.note = "No usable company website."
        return result
    domain = _root_domain(host)
    own_client = http is None
    http = http or httpx.Client(follow_redirects=True, timeout=10, headers={"User-Agent": USER_AGENT})
    try:
        robots = _Robots(http, base)
        queue: List[str] = [base] + [base + p for p in COMMON_PATHS]
        visited: List[str] = []
        candidates: Dict[str, Candidate] = {}
        while queue and len(visited) < MAX_PAGES:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.append(url)
            if not robots.allowed(url):
                log(f"Skipped {url} (disallowed by robots.txt)")
                continue
            try:
                r = http.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
                continue
            final_url = str(r.url)
            for email in find_emails_in_html(r.text):
                s = score_email(email, domain, final_url)
                if email not in candidates or candidates[email].score < s:
                    candidates[email] = Candidate(email, s, final_url)
            if url == base:  # follow links discovered on the homepage first
                queue = _candidate_links(r.text, base, domain) + queue
        result.pages_checked = visited
        ranked = sorted((c for c in candidates.values() if c.score > -100), key=lambda c: -c.score)
        if ranked and ranked[0].score >= HIRING_THRESHOLD:
            result.email, result.source = ranked[0].email, ranked[0].page
            result.alternatives = ranked[1:5]
        else:
            result.alternatives = ranked[:5]
            result.note = "No hiring-specific address published on the company site."
        return result
    finally:
        if own_client:
            http.close()


def find_website(company: str) -> str:
    """Look up the official homepage with web search. Returns '' if unsure."""
    text = web_search_text(
        f"Find the official company website for the employer named \"{company}\". "
        "Reply with one line: WEBSITE: <homepage URL>, or WEBSITE: NONE if you can't be sure which company this is."
    )
    m = re.search(r"WEBSITE:\s*(https?://\S+)", text)
    return m.group(1).rstrip(".,)") if m else ""


def find_hiring_email(company: str, website: str, log: Callable[[str], None]) -> Tuple[FinderResult, str]:
    """Returns the crawl result and the website that was used."""
    if not website and company:
        log(f"No website in the posting; looking up {company}'s official site")
        website = find_website(company)
    if not website:
        return FinderResult(note="Couldn't determine the company website."), ""
    log(f"Crawling careers and contact pages on {normalize_url(website)}")
    return crawl_for_email(website, log=log), normalize_url(website)
