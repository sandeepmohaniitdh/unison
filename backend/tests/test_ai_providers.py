"""GeminiProvider without the network: httpx.post is replaced by a fake Google."""

import json

import httpx
import pytest

from app.config import Settings
from app.modules.ai import providers
from app.modules.ai.providers import GeminiProvider, ProviderError, get_provider

REPLY = {"criteria": [{"criterion_id": 1, "points": 3, "comment": "Clear report."}]}
REQUEST = httpx.Request("POST", "https://generativelanguage.googleapis.com")


def answer(*parts):
    return httpx.Response(200, request=REQUEST, json={"candidates": [{"content": {"parts": list(parts)}}]})


def error(status, message="The model is overloaded."):
    return httpx.Response(status, request=REQUEST, json={"error": {"status": "UNAVAILABLE", "message": message}})


@pytest.fixture
def google(monkeypatch):
    """Answers per model, in order; records which model each call went to."""
    replies: dict[str, list] = {}
    calls: list[str] = []
    sent: list[dict] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        model = url.split("/models/")[1].split(":")[0]
        calls.append(model)
        sent.append({"body": json, "headers": headers})
        reply = replies[model].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    monkeypatch.setattr(providers.time, "sleep", lambda _seconds: None)
    return replies, calls, sent


def make(fallback="lite"):
    return GeminiProvider(' "AQ.key" ', "main", 60, fallback)


def test_good_answer_and_request_format(google):
    replies, calls, sent = google
    replies["main"] = [answer({"text": json.dumps(REPLY)})]
    assert make().generate("system", "prompt") == REPLY
    assert calls == ["main"]
    assert sent[0]["headers"]["x-goog-api-key"] == "AQ.key"  # spaces and quotes removed
    schema = sent[0]["body"]["generationConfig"]["responseSchema"]
    assert schema["type"] == "OBJECT"
    assert schema["properties"]["criteria"]["items"]["properties"]["points"]["type"] == "NUMBER"
    assert providers.REPLY_SCHEMA["type"] == "object"  # Ollama keeps the lowercase schema


def test_answer_in_several_parts_with_thoughts_and_fences(google):
    replies, _, _ = google
    text = "```json\n" + json.dumps(REPLY) + "\n```"
    replies["main"] = [answer({"text": "thinking...", "thought": True}, {"text": text[:20]}, {"text": text[20:]})]
    assert make().generate("s", "p") == REPLY


def test_busy_then_ok_retries_the_same_model(google):
    replies, calls, _ = google
    replies["main"] = [error(503), error(503), answer({"text": json.dumps(REPLY)})]
    assert make().generate("s", "p") == REPLY
    assert calls == ["main", "main", "main"]


def test_busy_main_model_falls_back(google):
    replies, calls, _ = google
    replies["main"] = [error(503)] * 4
    replies["lite"] = [answer({"text": json.dumps(REPLY)})]
    assert make().generate("s", "p") == REPLY
    assert calls == ["main"] * 4 + ["lite"]


def test_slow_main_model_falls_back(google):
    replies, calls, _ = google
    replies["main"] = [httpx.ReadTimeout("slow")]
    replies["lite"] = [answer({"text": json.dumps(REPLY)})]
    assert make().generate("s", "p") == REPLY
    assert calls == ["main", "lite"]


def test_both_models_busy_gives_googles_message(google):
    replies, _, _ = google
    replies["main"] = [error(503)] * 4
    replies["lite"] = [error(503)] * 4
    with pytest.raises(ProviderError) as exc:
        make().generate("s", "p")
    assert exc.value.code == "PROVIDER_ERROR"
    assert "HTTP 503: UNAVAILABLE The model is overloaded." in str(exc.value)


def test_no_fallback_configured(google):
    replies, calls, _ = google
    replies["main"] = [httpx.ReadTimeout("slow")]
    with pytest.raises(ProviderError) as exc:
        make(fallback="").generate("s", "p")
    assert exc.value.code == "TIMEOUT"
    assert calls == ["main"]


def test_quota_and_bad_key_are_not_retried(google):
    replies, calls, _ = google
    replies["main"] = [error(429, "Quota exceeded")]
    replies["lite"] = [error(401, "API key not valid")]
    with pytest.raises(ProviderError) as exc:
        make().generate("s", "p")
    assert exc.value.code == "PROVIDER_ERROR"
    assert "401" in str(exc.value)
    assert calls == ["main", "lite"]


def test_empty_answer_names_the_reason(google):
    replies, _, _ = google
    replies["main"] = [httpx.Response(200, request=REQUEST, json={"candidates": [{"finishReason": "SAFETY"}]})]
    with pytest.raises(ProviderError) as exc:
        make(fallback="").generate("s", "p")
    assert exc.value.code == "INVALID_OUTPUT"
    assert "SAFETY" in str(exc.value)


def test_answer_that_is_not_json(google):
    replies, _, _ = google
    replies["main"] = [answer({"text": "Sorry, I cannot help."})]
    with pytest.raises(ProviderError) as exc:
        make(fallback="").generate("s", "p")
    assert exc.value.code == "INVALID_OUTPUT"


def test_settings_build_the_provider():
    provider = get_provider(Settings(ai_provider="gemini", gemini_api_key="k"))
    assert isinstance(provider, GeminiProvider)
    assert (provider.model, provider.fallback_model, provider.timeout) == (
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        60.0,
    )
    assert get_provider(Settings(ai_provider="gemini", gemini_api_key="")) is None
