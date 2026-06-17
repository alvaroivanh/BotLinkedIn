"""OpenRouter backend.

Routes AI generation through OpenRouter's OpenAI-compatible Chat Completions API,
which exposes many models (e.g. Google Gemini Flash) behind a single API key.

Selected with ``AI_BACKEND=openrouter``. Requires ``OPENROUTER_API_KEY``. The
model is configurable via ``OPENROUTER_MODEL`` (default: a lightweight Gemini
Flash). This is an additive alternative to the default Anthropic ``api`` backend.
"""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class _Retryable(Exception):
    """Raised for transient HTTP failures (429 / 5xx) so tenacity retries them."""


class OpenRouterClient:
    """Drop-in replacement for ``ClaudeClient`` backed by OpenRouter."""

    def __init__(self):
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "AI_BACKEND=openrouter requires OPENROUTER_API_KEY to be set in your .env."
            )
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Optional attribution headers recommended by OpenRouter.
            "HTTP-Referer": "https://github.com/alvaroivanh/BotLinkedIn",
            "X-Title": "BotLinkedIn",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((_Retryable, httpx.TransportError)),
    )
    def _call(self, system: str, user: str, max_tokens: int) -> tuple[str, int]:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        resp = httpx.post(OPENROUTER_URL, headers=self._headers(), json=body, timeout=120)

        if resp.status_code == 429 or resp.status_code >= 500:
            raise _Retryable(f"{resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()  # non-retryable 4xx -> surface immediately

        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"OpenRouter error: {data['error']}")

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        total = int(
            usage.get("total_tokens")
            or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
        )
        return text, total

    def generate(self, system: str, user: str, max_tokens: int = 4096) -> str:
        text, _ = self._call(system, user, max_tokens)
        return text

    def generate_with_usage(
        self, system: str, user: str, max_tokens: int = 4096
    ) -> tuple[str, int]:
        return self._call(system, user, max_tokens)
