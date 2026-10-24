from app.agents.tailor import assemble
from app.schemas import (Education, Experience, ResumeData, TailoredBullet, TailoredExperience,
                         TailoredSkill, TailorOutput)

BASE = ResumeData(
    name="Jane Doe", email="jane@example.com", skills=["Python", "SQL"],
    experience=[
        Experience(company="Acme", title="Engineer", start="2021", end="Present", bullets=["Built APIs"]),
        Experience(company="Initech", title="Intern", start="2020", end="2021", bullets=["Fixed bugs"]),
    ],
    education=[Education(institution="State U", degree="BSc")],
)


def _out(**kw):
    defaults = dict(summary="Backend engineer.", skills=[], experience=[], projects=[])
    defaults.update(kw)
    return TailorOutput(**defaults)


def test_employers_titles_dates_come_from_base():
    out = _out(experience=[
        TailoredExperience(base_index=0, bullets=[TailoredBullet(text="Built REST APIs in FastAPI", provenance="reworded")]),
        TailoredExperience(base_index=7, bullets=[TailoredBullet(text="Invented job", provenance="inferred")]),
    ])
    r = assemble(BASE, out, [])
    assert [(e["company"], e["title"], e["start"], e["end"]) for e in r["experience"]] == [
        ("Acme", "Engineer", "2021", "Present"), ("Initech", "Intern", "2020", "2021")]
    assert "Invented job" not in str(r)
    assert r["education"] == [e.model_dump() for e in BASE.education]


def test_omitted_role_keeps_original_bullets():
    r = assemble(BASE, _out(), [])
    assert r["experience"][1]["bullets"] == [{"text": "Fixed bugs", "provenance": "original"}]


def test_skill_provenance_is_recomputed():
    out = _out(skills=[TailoredSkill(name="python", provenance="inferred"),
                       TailoredSkill(name="Docker", provenance="original"),
                       TailoredSkill(name="Kubernetes", provenance="inferred"),
                       TailoredSkill(name="Docker", provenance="inferred")])
    r = assemble(BASE, out, extra_skills=["Docker"])
    assert r["skills"] == [{"name": "python", "provenance": "original"},
                           {"name": "Docker", "provenance": "original"},
                           {"name": "Kubernetes", "provenance": "inferred"}]


def test_unchanged_bullet_is_original_and_false_original_becomes_reworded():
    out = _out(experience=[TailoredExperience(base_index=0, bullets=[
        TailoredBullet(text="Built  APIs", provenance="reworded"),
        TailoredBullet(text="Built APIs for payments", provenance="original"),
    ])])
    bullets = assemble(BASE, out, [])["experience"][0]["bullets"]
    assert bullets == [{"text": "Built APIs", "provenance": "original"},
                       {"text": "Built APIs for payments", "provenance": "reworded"}]
