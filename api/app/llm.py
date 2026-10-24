"""Thin wrapper over the model providers used by every agent: one structured call per step.

The provider is chosen by LLM_PROVIDER (gemini | claude). Agents only use `structured`,
`web_search_text` and the neutral block helpers, so they don't know which model answers."""
from __future__ import annotations

import base64
import time
from functools import lru_cache
from typing import Any, List, Literal, Optional, Type, TypeVar

import anthropic
import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from .config import get_settings

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high", "xhigh", "max"]

# Claude server-side refusal fallback, routed by refusal category.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# The Gemini free tier has per-minute limits; wait and retry before giving up.
_RETRY_DELAYS = (8.0, 25.0)


class LLMError(Exception):
    """A model call that produced no usable output. The message is safe to show the user."""


# ---- Provider-neutral content blocks --------------------------------------------

def image_block(data: bytes, media_type: str) -> dict:
    return {"type": "image", "media_type": media_type, "data": data}


def document_block(pdf: bytes) -> dict:
    return {"type": "document", "media_type": "application/pdf", "data": pdf}


def _provider() -> str:
    provider = get_settings().llm_provider.lower()
    if provider not in ("gemini", "claude"):
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use 'gemini' or 'claude'.")
    return provider


def structured(
    system: str,
    content: List[Any],
    schema: Type[T],
    *,
    effort: Effort = "medium",
    max_tokens: int = 16000,
) -> T:
    """Run one request whose output is validated against `schema`."""
    if _provider() == "claude":
        return _claude_structured(system, content, schema, effort, max_tokens)
    return _gemini_structured(system, content, schema, max_tokens)


def web_search_text(prompt: str) -> str:
    """Answer `prompt` with live web search and return the reply text ('' if nothing usable)."""
    try:
        return _claude_web_search(prompt) if _provider() == "claude" else _gemini_web_search(prompt)
    except LLMError:
        return ""


# ---- Gemini -----------------------------------------------------------------------

@lru_cache
def _gemini() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def _gemini_parts(content: List[Any]) -> List[genai_types.Part]:
    parts = []
    for block in content:
        if block["type"] == "text":
            parts.append(genai_types.Part.from_text(text=block["text"]))
        else:
            parts.append(genai_types.Part.from_bytes(data=block["data"], mime_type=block["media_type"]))
    return parts


def _gemini_generate(contents: Any, config: genai_types.GenerateContentConfig) -> genai_types.GenerateContentResponse:
    if not get_settings().gemini_api_key:
        raise LLMError("Gemini API key is missing. Set GEMINI_API_KEY in api/.env (free key: aistudio.google.com/apikey).")
    attempt = 0
    while True:
        try:
            return _gemini().models.generate_content(model=get_settings().gemini_model, contents=contents, config=config)
        except genai_errors.APIError as e:
            code = e.code or 0
            if code in (429, 500, 503) and attempt < len(_RETRY_DELAYS):
                time.sleep(_RETRY_DELAYS[attempt])
                attempt += 1
                continue
            if code in (401, 403) or (code == 400 and "API key" in str(e.message)):
                raise LLMError("Gemini API key is missing or invalid. Check GEMINI_API_KEY in api/.env.") from e
            if code == 429:
                raise LLMError("Gemini's free-tier limit was reached (per minute or per day). Try again later.") from e
            if code == 404:
                raise LLMError(f"Gemini model '{get_settings().gemini_model}' wasn't found. Check GEMINI_MODEL.") from e
            if code == 400:
                raise LLMError(f"Gemini rejected the request: {e.message}") from e
            if code == 504:
                raise LLMError("Gemini took too long to answer. Try again, or set a faster GEMINI_MODEL.") from e
            raise LLMError(f"Gemini API error ({code}).") from e
        except httpx.HTTPError as e:
            raise LLMError("Could not reach the Gemini API.") from e


def _gemini_text(response: genai_types.GenerateContentResponse) -> str:
    feedback = response.prompt_feedback
    if feedback and feedback.block_reason:
        raise LLMError("Gemini declined this request.")
    candidate = response.candidates[0] if response.candidates else None
    if candidate is None:
        raise LLMError("Gemini returned no answer.")
    if candidate.finish_reason == genai_types.FinishReason.MAX_TOKENS:
        raise LLMError("The model ran out of output space before finishing.")
    if candidate.finish_reason in (genai_types.FinishReason.SAFETY, genai_types.FinishReason.PROHIBITED_CONTENT,
                                   genai_types.FinishReason.RECITATION):
        raise LLMError("Gemini declined this request.")
    text = response.text
    if not text:
        raise LLMError("Gemini returned an empty answer.")
    return text


def _gemini_structured(system: str, content: List[Any], schema: Type[T], max_tokens: int) -> T:
    config = genai_types.GenerateContentConfig(
        system_instruction=system, response_mime_type="application/json", response_schema=schema,
        max_output_tokens=max_tokens,
    )
    response = _gemini_generate([genai_types.Content(role="user", parts=_gemini_parts(content))], config)
    try:
        return schema.model_validate_json(_gemini_text(response))
    except ValidationError as e:
        raise LLMError("The model returned output that didn't match the expected format.") from e


def _gemini_web_search(prompt: str) -> str:
    config = genai_types.GenerateContentConfig(
        tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())], max_output_tokens=4000,
    )
    return _gemini_text(_gemini_generate(prompt, config))


# ---- Claude -----------------------------------------------------------------------

@lru_cache
def client() -> anthropic.Anthropic:
    # Key from api/.env if set; otherwise the SDK resolves ANTHROPIC_API_KEY or an `ant auth login` profile.
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key or None, max_retries=3)


def _claude_content(content: List[Any]) -> List[dict]:
    blocks = []
    for block in content:
        if block["type"] == "text":
            blocks.append(block)
        else:
            blocks.append({"type": block["type"], "source": {
                "type": "base64", "media_type": block["media_type"],
                "data": base64.standard_b64encode(block["data"]).decode()}})
    return blocks


def _claude_structured(system: str, content: List[Any], schema: Type[T], effort: Effort, max_tokens: int) -> T:
    try:
        response = client().beta.messages.parse(
            model=get_settings().claude_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": _claude_content(content)}],
            output_format=schema,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        raise LLMError("Claude API credentials are missing or invalid. Set ANTHROPIC_API_KEY.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Claude API rate limit reached. Try again shortly.") from e
    except anthropic.BadRequestError as e:
        raise LLMError(f"Claude API rejected the request: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Claude API.") from e

    if response.stop_reason == "refusal":
        raise LLMError("The model declined this request.")
    if response.stop_reason == "max_tokens":
        raise LLMError("The model ran out of output space before finishing.")
    parsed: Optional[T] = response.parsed_output
    if parsed is None:
        raise LLMError("The model returned output that didn't match the expected format.")
    return parsed


def _claude_web_search(prompt: str) -> str:
    messages: List[dict] = [{"role": "user", "content": prompt}]
    try:
        for _ in range(3):  # resume server-tool turns that pause
            response = client().beta.messages.create(
                model=get_settings().claude_model,
                max_tokens=4000,
                messages=messages,
                tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}],
                output_config={"effort": "low"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
    except anthropic.APIError as e:
        raise LLMError("Claude web search failed.") from e
    if response.stop_reason == "refusal":
        raise LLMError("The model declined this request.")
    return " ".join(b.text for b in response.content if b.type == "text")
