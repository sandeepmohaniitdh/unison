"""The AI model behind a small interface, with three implementations:

- GeminiProvider: Google's Gemini API (structured JSON output).
- OllamaProvider: a local open-weights model, so nothing leaves the machine.
- FakeProvider: for tests and demos; never calls anything.

Every provider gets the same prompt and must return JSON that matches
REPLY_SCHEMA. The service validates and clamps the reply afterwards, so a
provider is never trusted.
"""

import json

import httpx

from app.config import Settings


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

    def __init__(self, api_key: str, model: str, timeout: float):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, system: str, prompt: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": REPLY_SCHEMA,
            },
        }
        try:
            response = httpx.post(url, json=body, headers={"x-goog-api-key": self.api_key}, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise ProviderError("TIMEOUT", "The model did not answer in time.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("PROVIDER_ERROR", str(exc)) from exc
        if response.status_code == 429:
            raise ProviderError("QUOTA_EXHAUSTED", "The model's quota is used up.")
        if response.status_code != 200:
            raise ProviderError("PROVIDER_ERROR", f"HTTP {response.status_code}")
        try:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError("INVALID_OUTPUT", "The model's answer was not valid JSON.") from exc


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
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model, settings.ai_timeout_seconds)
    if settings.ai_provider == "ollama":
        return OllamaProvider(settings.ollama_url, settings.ollama_model, settings.ai_timeout_seconds)
    return FakeProvider()


def model_name(settings: Settings) -> str:
    return {
        "gemini": settings.gemini_model,
        "ollama": settings.ollama_model,
        "fake": FakeProvider.model,
    }.get(settings.ai_provider, "none")
