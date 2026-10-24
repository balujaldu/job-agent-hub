"""The Gemini provider with the Google client faked: parsing, content conversion, error mapping."""
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app import llm
from app.agents import email_finder
from app.config import get_settings
from app.schemas import Drafts


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def reply(text, finish=genai_types.FinishReason.STOP, block=None):
    return SimpleNamespace(text=text, prompt_feedback=SimpleNamespace(block_reason=block),
                           candidates=[SimpleNamespace(finish_reason=finish)])


def api_error(code, message="boom"):
    return genai_errors.APIError(code, {"error": {"message": message}})


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")
    monkeypatch.setattr(llm, "_RETRY_DELAYS", (0.0, 0.0))

    def install(*outcomes):
        models = FakeModels(outcomes)
        monkeypatch.setattr(llm, "_gemini", lambda: SimpleNamespace(models=models))
        return models

    return install


DRAFTS = '{"email_subject": "Hi", "email_body": "Body"}'


def test_structured_parses_json_and_sends_neutral_blocks(gemini):
    models = gemini(reply(DRAFTS))
    content = [llm.image_block(b"png-bytes", "image/png"), llm.document_block(b"%PDF"), {"type": "text", "text": "Extract."}]
    result = llm.structured("system prompt", content, Drafts)
    assert isinstance(result, Drafts) and result.email_subject == "Hi"

    call = models.calls[0]
    assert call["model"] == get_settings().gemini_model
    assert call["config"].system_instruction == "system prompt"
    assert call["config"].response_mime_type == "application/json"
    parts = call["contents"][0].parts
    assert parts[0].inline_data.mime_type == "image/png" and parts[0].inline_data.data == b"png-bytes"
    assert parts[1].inline_data.mime_type == "application/pdf"
    assert parts[2].text == "Extract."


@pytest.mark.parametrize("outcome, message", [
    (api_error(401), "missing or invalid"),
    (api_error(403), "missing or invalid"),
    (api_error(404), "wasn't found"),
    (api_error(400, "bad prompt"), "rejected the request"),
    (api_error(500), r"Gemini API error \(500\)"),
    (reply("{"), "didn't match"),
    (reply(DRAFTS, finish=genai_types.FinishReason.MAX_TOKENS), "ran out of output space"),
    (reply("", finish=genai_types.FinishReason.SAFETY), "declined"),
    (reply("", block="SAFETY"), "declined"),
])
def test_structured_errors_become_llm_errors(gemini, outcome, message):
    gemini(*([outcome] * 3))
    with pytest.raises(llm.LLMError, match=message):
        llm.structured("s", [{"type": "text", "text": "x"}], Drafts)


def test_rate_limit_retries_then_succeeds_or_reports(gemini):
    models = gemini(api_error(429), reply(DRAFTS))
    assert llm.structured("s", [{"type": "text", "text": "x"}], Drafts).email_body == "Body"
    assert len(models.calls) == 2

    gemini(api_error(429), api_error(429), api_error(429))
    with pytest.raises(llm.LLMError, match="free-tier limit"):
        llm.structured("s", [{"type": "text", "text": "x"}], Drafts)


def test_missing_key_is_reported_without_calling_google(gemini, monkeypatch):
    models = gemini(reply(DRAFTS))
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY"):
        llm.structured("s", [{"type": "text", "text": "x"}], Drafts)
    assert models.calls == []


def test_unknown_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "nope")
    with pytest.raises(llm.LLMError, match="LLM_PROVIDER"):
        llm.structured("s", [{"type": "text", "text": "x"}], Drafts)


def test_web_search_uses_google_search_and_find_website_parses_it(gemini):
    models = gemini(reply("WEBSITE: https://globex.com/."), api_error(401))
    assert email_finder.find_website("Globex") == "https://globex.com/"
    assert models.calls[0]["config"].tools[0].google_search is not None
    assert email_finder.find_website("Globex") == ""  # a failed search just means no website


def test_claude_content_conversion():
    blocks = llm._claude_content([llm.image_block(b"abc", "image/png"), {"type": "text", "text": "hi"}])
    assert blocks[0] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "YWJj"}}
    assert blocks[1] == {"type": "text", "text": "hi"}
