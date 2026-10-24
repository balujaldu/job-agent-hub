"""End-to-end API flow with Claude, Gmail and the browser replaced by fakes."""
import io

import pytest
from fastapi.testclient import TestClient

from app import gmail, outbox, render, worker
from app.agents import composer, email_finder, extractor, resume_reader, tailor
from app.agents.email_finder import FinderResult
from app.main import app
from app.schemas import (Drafts, Education, Experience, JobExtraction, ResumeData, TailoredBullet,
                         TailoredExperience, TailoredSkill, TailorOutput)

RESUME = ResumeData(
    name="Jane Doe", email="jane@example.com", phone="555-0100", skills=["Python"],
    experience=[Experience(company="Acme", title="Engineer", start="2021", end="Present", bullets=["Built APIs"])],
    education=[Education(institution="State U", degree="BSc")],
)


def fake_extraction(emails):
    return JobExtraction(company="Globex", role="Backend Engineer", location="Remote", company_website="globex.com",
                         job_url="", jd_text="Python FastAPI PostgreSQL", emails=emails, recruiter_name="",
                         keywords=["python", "fastapi", "postgresql"])


@pytest.fixture
def env(monkeypatch, tmp_path):
    sent = []
    state = {"emails": ["jobs@globex.com"], "found": ""}
    monkeypatch.setattr(worker, "submit", lambda fn, *a: fn(*a))  # run background work inline
    monkeypatch.setattr(resume_reader, "parse_resume", lambda data, suffix, text: RESUME)
    monkeypatch.setattr(resume_reader, "extract_text", lambda data, suffix: "Jane Doe resume text")
    monkeypatch.setattr(extractor, "extract_job", lambda *a, **k: fake_extraction(state["emails"]))
    monkeypatch.setattr(tailor, "tailor", lambda *a, **k: TailorOutput(
        summary="Python engineer.", skills=[TailoredSkill(name="FastAPI", provenance="inferred")],
        experience=[TailoredExperience(base_index=0, bullets=[TailoredBullet(text="Built FastAPI services on PostgreSQL", provenance="reworded")])],
        projects=[]))
    monkeypatch.setattr(render, "to_pdf", lambda r: b"%PDF-1.4 fake")
    monkeypatch.setattr(email_finder, "find_hiring_email",
                        lambda company, site, log: (FinderResult(email=state["found"], source="https://globex.com/careers"), "https://globex.com"))
    monkeypatch.setattr(composer, "compose", lambda job, t: Drafts(
        email_subject="Application: Backend Engineer - Jane Doe", email_body="Hi Globex hiring team, ..."))
    monkeypatch.setattr(gmail, "connected_address", lambda db, uid: "jane@gmail.com")
    monkeypatch.setattr(gmail, "send", lambda db, uid, to, subject, body, att: sent.append(to) or "msg-1")
    with TestClient(app) as client:
        yield client, sent, state


def _onboard(client):
    r = client.post("/api/auth/register", json={"email": "jane@example.com", "password": "correct-horse"})
    if r.status_code == 403:
        r = client.post("/api/auth/login", json={"email": "jane@example.com", "password": "correct-horse"})
    assert r.status_code == 200, r.text
    r = client.post("/api/resume", files={"file": ("cv.pdf", io.BytesIO(b"%PDF"), "application/pdf")})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    r = client.put(f"/api/resume/{rid}", json={"data": RESUME.model_dump(), "extra_skills": ["Docker"], "confirmed": True})
    assert r.status_code == 200


def test_requires_login(env):
    client, _, _ = env
    client.cookies.clear()
    assert client.get("/api/jobs").status_code == 401


def test_full_flow_sends_only_after_approval(env):
    client, sent, _ = env
    _onboard(client)
    job = client.post("/api/jobs", data={"text": "Backend role at Globex. Email jobs@globex.com"}).json()
    detail = client.get(f"/api/jobs/{job['id']}").json()

    assert detail["status"] == "awaiting_approval"
    assert detail["to_email"] == "jobs@globex.com"
    assert detail["ats_after"] > detail["ats_before"]
    assert detail["tailored"]["experience"][0]["company"] == "Acme"
    assert sent == []  # nothing goes out before approval

    r = client.post(f"/api/jobs/{job['id']}/approve-email")
    assert r.status_code == 200
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "sent"
    assert sent == ["jobs@globex.com"]

    # A second approval can't send again.
    assert client.post(f"/api/jobs/{job['id']}/approve-email").status_code == 409
    assert sent == ["jobs@globex.com"]


def test_email_not_found_then_user_supplies_address(env):
    client, sent, state = env
    state["emails"], state["found"] = [], ""
    _onboard(client)
    job_id = client.post("/api/jobs", data={"text": "Backend role at Globex"}).json()["id"]
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "email_not_found"
    assert detail["email_body"] and detail["has_pdf"]  # drafts still produced

    assert client.post(f"/api/jobs/{job_id}/approve-email").status_code == 409
    r = client.patch(f"/api/jobs/{job_id}", json={"to_email": "hr@globex.com"})
    assert r.json()["status"] == "awaiting_approval"
    assert sent == []


def test_terminated_job_cannot_be_sent(env):
    client, sent, _ = env
    _onboard(client)
    job_id = client.post("/api/jobs", data={"text": "role"}).json()["id"]
    assert client.post(f"/api/jobs/{job_id}/terminate").json()["status"] == "terminated"
    assert client.post(f"/api/jobs/{job_id}/approve-email").status_code == 409
    outbox.send_email(job_id)  # even a direct call refuses
    assert sent == []


def test_paused_sending_blocks_approval(env):
    client, sent, _ = env
    _onboard(client)
    job_id = client.post("/api/jobs", data={"text": "role"}).json()["id"]
    client.put("/api/settings", json={"sending_paused": True})
    r = client.post(f"/api/jobs/{job_id}/approve-email")
    assert r.status_code == 409 and "paused" in r.json()["detail"]
    client.put("/api/settings", json={"sending_paused": False})
    assert sent == []


def test_only_one_account(env):
    client, _, _ = env
    _onboard(client)
    r = client.post("/api/auth/register", json={"email": "other@example.com", "password": "another-pass"})
    assert r.status_code == 403
