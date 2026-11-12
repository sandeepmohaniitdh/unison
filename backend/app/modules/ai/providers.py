"""The AI model behind a small interface, with three implementations:

- GeminiProvider: Google's Gemini API (structured JSON output).
- OllamaProvider: a local open-weights model, so nothing leaves the machine.
- FakeProvider: for tests and demos; never calls anything.

Every provider gets the same prompt and must return JSON that matches
REPLY_SCHEMA. The service validates and clamps the reply afterwards, so a
provider is never trusted.
"""

import json
import logging
import time

import httpx

from app.config import Settings


log = logging.getLogger("unison.ai")

# Waits (seconds) between attempts when Google is busy; None marks the last attempt.
RETRY_WAITS = (3, 10, 20, None)
RETRY_STATUSES = {500, 502, 503, 504}
# Errors after which the fallback model is worth a try (busy, too slow, or this model's quota used up).
SWITCH_MODEL_CODES = {"PROVIDER_ERROR", "TIMEOUT", "QUOTA_EXHAUSTED"}


class ProviderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "integer"},
                    "points": {"type": "number"},
                    "comment": {"type": "string"},
                },
                "required": ["criterion_id", "points", "comment"],
            },
        }
    },
    "required": ["criteria"],
}


class Provider:
    name = "none"
    model = "none"

    def generate(self, system: str, prompt: str) -> dict:
        raise NotImplementedError


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float, fallback_model: str = ""):
        self.api_key = api_key.strip().strip('"').strip("'")
        self.model = model
        self.timeout = timeout
        self.fallback_model = fallback_model.strip()

    def generate(self, system: str, prompt: str) -> dict:
        """Ask the main model; if it is overloaded, too slow or out of quota, ask the fallback model."""
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)
        for i, model in enumerate(models):
            try:
                return self._generate_with(model, system, prompt)
            except ProviderError as exc:
                last_try = i == len(models) - 1
                if last_try or exc.code not in SWITCH_MODEL_CODES:
                    raise
                log.warning("Gemini model %s failed (%s: %s); trying %s", model, exc.code, exc, models[i + 1])
        raise AssertionError("unreachable")

    def _generate_with(self, model: str, system: str, prompt: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                # Gemini's responseSchema uses OpenAPI type names in capitals (OBJECT, ARRAY, ...).
                "responseSchema": _gemini_schema(REPLY_SCHEMA),
            },
        }
        # 500/503 mean Google is busy ("model overloaded"); it usually works a few seconds later.
        for wait in RETRY_WAITS:
            try:
                response = httpx.post(url, json=body, headers={"x-goog-api-key": self.api_key}, timeout=self.timeout)
            except httpx.TimeoutException as exc:
                raise ProviderError("TIMEOUT", f"Gemini ({model}) did not answer within {self.timeout:g} s.") from exc
            except httpx.HTTPError as exc:
                raise ProviderError("PROVIDER_ERROR", f"Could not reach Gemini: {exc}") from exc
            if response.status_code not in RETRY_STATUSES or wait is None:
                break
            log.warning("Gemini (%s) answered HTTP %s, trying again in %s s", model, response.status_code, wait)
            time.sleep(wait)
        if response.status_code == 429:
            raise ProviderError("QUOTA_EXHAUSTED", f"HTTP 429: {_google_error(response)}")
        if response.status_code != 200:
            # The worker log shows this message, so the real reason (bad key, unknown model, ...) is visible.
            raise ProviderError("PROVIDER_ERROR", f"HTTP {response.status_code}: {_google_error(response)}")
        try:
            data = response.json()
            candidate = data["candidates"][0]
            # Thinking models can split the answer over several parts; "thought" parts are not the answer.
            text = "".join(
                p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if not p.get("thought")
            )
            if not text.strip():
                reason = candidate.get("finishReason", "unknown")
                raise ProviderError("INVALID_OUTPUT", f"Gemini returned no text (finishReason={reason}).")
            return json.loads(_strip_fences(text))
        except ProviderError:
            raise
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ProviderError("INVALID_OUTPUT", f"The model's answer was not valid JSON: {exc}") from exc


def _gemini_schema(schema):
    """REPLY_SCHEMA with the type names Gemini's responseSchema expects."""
    if isinstance(schema, dict):
        return {k: (v.upper() if k == "type" and isinstance(v, str) else _gemini_schema(v)) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_gemini_schema(v) for v in schema]
    return schema


def _google_error(response: httpx.Response) -> str:
    try:
        error = response.json()["error"]
        return f"{error.get('status', '')} {error.get('message', '')}".strip()[:500]
    except (KeyError, ValueError, TypeError):
        return response.text[:500]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, system: str, prompt: str) -> dict:
        body = {
            "model": self.model,
            "stream": False,
            "format": REPLY_SCHEMA,
            "options": {"temperature": 0.2},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=body, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise ProviderError("TIMEOUT", "The model did not answer in time.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("PROVIDER_ERROR", str(exc)) from exc
        if response.status_code != 200:
            raise ProviderError("PROVIDER_ERROR", f"HTTP {response.status_code}")
        try:
            return json.loads(response.json()["message"]["content"])
        except (KeyError, ValueError) as exc:
            raise ProviderError("INVALID_OUTPUT", "The model's answer was not valid JSON.") from exc


class FakeProvider(Provider):
    """Suggests 70% of each criterion's maximum. Tests can pass a fixed reply or an error."""

    name = "fake"
    model = "fake-model"

    def __init__(self, reply: dict | None = None, error: ProviderError | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[str] = []

    def generate(self, system: str, prompt: str) -> dict:
        self.calls.append(prompt)
        if self.error:
            raise self.error
        if self.reply is not None:
            return self.reply
        criteria = json.loads(prompt.split("RUBRIC_JSON:", 1)[1].split("\n", 1)[0])
        return {
            "criteria": [
                {
                    "criterion_id": c["id"],
                    "points": round(c["max_points"] * 0.7, 1),
                    "comment": "Meets most of the criterion.",
                }
                for c in criteria
            ]
        }


def get_provider(settings: Settings) -> Provider | None:
    if not settings.ai_enabled:
        return None
    if settings.ai_provider == "gemini":
        return GeminiProvider(
            settings.gemini_api_key, settings.gemini_model, settings.ai_timeout_seconds, settings.gemini_fallback_model
        )
    if settings.ai_provider == "ollama":
        return OllamaProvider(settings.ollama_url, settings.ollama_model, settings.ai_timeout_seconds)
    return FakeProvider()


def model_name(settings: Settings) -> str:
    return {
        "gemini": settings.gemini_model,
        "ollama": settings.ollama_model,
        "fake": FakeProvider.model,
    }.get(settings.ai_provider, "none")
