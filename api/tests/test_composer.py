"""The composer's layout and signature are enforced in code, whatever the model returns."""
from app.agents import composer
from app.schemas import EmailParts

TAILORED = {
    "name": "JALDU BALASUBRAMANYAM GUPTHA", "phone": "+91 98765 43210", "email": "me@example.com",
    "links": ["https://github.com/me"], "summary": "Backend engineer.", "skills": [{"name": "Python"}],
    "experience": [{"company": "Acme", "title": "Engineer", "bullets": [{"text": "Built APIs"}]}],
}


def test_email_is_structured_and_signed_with_name_only(monkeypatch):
    seen = {}

    def fake_structured(system, content, schema, **kw):
        seen["prompt"] = content[0]["text"]
        return EmailParts(
            subject="Application for Backend Engineer at Globex.",
            greeting="Dear Globex Hiring Team,",
            paragraphs=["I'm applying for the Backend Engineer role.",
                        "I build Python APIs. Call me on +91 98765 43210 or me@example.com, see https://github.com/me.",
                        "My resume is attached."],
            sign_off="Best regards,",
        )

    monkeypatch.setattr(composer, "structured", fake_structured)
    drafts = composer.compose({"company": "Globex", "role": "Backend Engineer"}, TAILORED)

    assert drafts.email_subject == "Application for Backend Engineer at Globex"
    assert drafts.email_body.startswith("Dear Globex Hiring Team,\n\nI'm applying")
    assert drafts.email_body.endswith("\n\nBest regards,\nJaldu Balasubramanyam Guptha")
    assert drafts.email_body.count("\n\n") == 4  # greeting / 3 paragraphs / sign-off
    for contact in ("98765", "me@example.com", "github.com"):
        assert contact not in drafts.email_body
        assert contact not in seen["prompt"]  # the model never sees contact details


def test_display_name_keeps_mixed_case():
    assert composer.display_name("Jaldu Balasubramanyam Guptha") == "Jaldu Balasubramanyam Guptha"
    assert composer.display_name("  JALDU   GUPTHA ") == "Jaldu Guptha"
