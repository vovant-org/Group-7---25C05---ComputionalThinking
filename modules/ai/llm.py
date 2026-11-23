"""Free text-model providers. Both return the model's raw text; `reader.py` parses and validates it.

PollinationsLLM  no key (anonymous tier, rate limited). The prompt is sent to Pollinations.
GeminiLLM        free key from Google AI Studio (GEMINI_API_KEY). Free tier text models only; the free tier
                 may use your prompts to improve Google products (see Google's pricing page).
Both send the user's text to an online service: the caller must have the user's consent (`allow_online`).
"""
from __future__ import annotations

import json
import os
from typing import Optional, Protocol

from modules.ai.net import AIError, http_request


class LLM(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


class PollinationsLLM:
    """OpenAI-compatible chat endpoint of Pollinations (anonymous tier)."""
    name = "pollinations-text"

    def __init__(self, url: str = "https://text.pollinations.ai/openai", model: str = "openai",
                 api_key: Optional[str] = None, timeout: float = 120.0):
        self.url, self.model, self.timeout = url, model, timeout
        self.api_key = api_key if api_key is not None else os.environ.get("POLLINATIONS_API_KEY", "")

    def complete(self, system: str, user: str) -> str:
        body = {"model": self.model, "temperature": 0.2, "seed": 7,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        raw = http_request(self.url, data=json.dumps(body).encode("utf-8"), headers=headers, timeout=self.timeout)
        try:
            return json.loads(raw)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIError(f"unexpected answer from Pollinations: {raw[:120]!r}") from exc


class GeminiLLM:
    """Gemini API through a free AI Studio key. The model name can change: set GEMINI_TEXT_MODEL to override."""
    name = "gemini-text"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, timeout: float = 120.0):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
        self.timeout = timeout
        if not self.api_key:
            raise AIError("GEMINI_API_KEY is not set (create a free key at https://aistudio.google.com/apikey)")

    def complete(self, system: str, user: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
        raw = http_request(url, data=json.dumps(body).encode("utf-8"), timeout=self.timeout,
                           headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key})
        try:
            return json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIError(f"unexpected answer from Gemini: {raw[:120]!r}") from exc


class FallbackLLM:
    """Try the providers in order; the first one that answers wins (Gemini busy -> Pollinations)."""
    name = "auto"

    def __init__(self, providers: list):
        self.providers, self.used = providers, ""

    def complete(self, system: str, user: str) -> str:
        last: Optional[AIError] = None
        for p in self.providers:
            try:
                out = p.complete(system, user)
                self.used = p.name
                self.name = f"auto({p.name})"
                return out
            except AIError as exc:
                last = exc
        raise last or AIError("no AI reader is available")


LLM_CHOICES = ("off", "auto", "pollinations", "gemini")


def make_llm(kind: str) -> Optional[LLM]:
    if kind == "off":
        return None
    if kind == "auto":                                   # Gemini when a key is set, then Pollinations
        chain: list = []
        if os.environ.get("GEMINI_API_KEY", "").strip():
            chain.append(GeminiLLM())
        return FallbackLLM(chain + [PollinationsLLM()])
    if kind == "pollinations":
        return PollinationsLLM()
    if kind == "gemini":
        return GeminiLLM()
    raise AIError(f"unknown AI reader {kind!r}; choose one of {', '.join(LLM_CHOICES)}")
