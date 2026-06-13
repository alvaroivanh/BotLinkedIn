"""Claude Agent SDK backend.

Alternative AI backend that routes generation through the **Claude Agent SDK**
(the same engine that powers the Claude Code CLI) instead of calling the
Anthropic Messages API directly.

It is selected by setting ``AI_BACKEND=agent`` in the environment. The default
backend (``api``, implemented in :mod:`src.ai.client`) is left untouched.

Authentication
--------------
This backend authenticates Claude Code with your **own Anthropic API key**
(``ANTHROPIC_API_KEY``). The key is passed explicitly to the SDK so usage is
billed to your API account. An API key is therefore required for this backend;
if it is missing we fail fast with a clear message instead of silently falling
back to any other credential.

Concurrency
-----------
``generate``/``generate_with_usage`` are synchronous to stay drop-in compatible
with :class:`src.ai.client.ClaudeClient`. The SDK is async, and these methods are
sometimes called from *within* a running event loop (e.g. the Playwright form
filler). To work in both situations we run the SDK coroutine in a dedicated
worker thread that owns its own event loop, and block until it finishes.
"""

from __future__ import annotations

import asyncio
import os
import threading

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from src.config import settings


class AgentClient:
    """Drop-in replacement for ``ClaudeClient`` backed by the Claude Agent SDK."""

    def __init__(self):
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "AI_BACKEND=agent requires ANTHROPIC_API_KEY to be set in your .env "
                "(the Agent SDK is authenticated with your Anthropic API key)."
            )
        self.model = settings.claude_model

    # ── Options ────────────────────────────────────────────────
    def _options(self, system: str) -> ClaudeAgentOptions:
        # Preserve the current environment (PATH, etc.) and force the API key so
        # billing goes to the API account rather than any logged-in session.
        env = {**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key}
        return ClaudeAgentOptions(
            system_prompt=system,
            model=self.model,
            max_turns=1,            # single completion, no agentic loop
            allowed_tools=[],       # pure text generation, no tools
            permission_mode="default",
            setting_sources=[],     # ignore global/project Claude settings for a clean call
            env=env,
        )

    # ── Async core ─────────────────────────────────────────────
    async def _run(self, system: str, user: str) -> tuple[str, int]:
        text_parts: list[str] = []
        total_tokens = 0
        async for message in query(prompt=user, options=self._options(system)):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    raise RuntimeError(
                        f"Claude Agent SDK error: {message.result or message.errors}"
                    )
                # ResultMessage.result holds the final assistant text; prefer it.
                if message.result:
                    text_parts = [message.result]
                total_tokens = _usage_tokens(message.usage)
        return "".join(text_parts), total_tokens

    # ── Sync bridge ────────────────────────────────────────────
    def _run_blocking(self, system: str, user: str) -> tuple[str, int]:
        """Run the async core to completion, even if an event loop is active.

        We always spawn a fresh thread so ``asyncio.run`` has no running loop to
        clash with, which makes this safe both from plain sync code and from
        inside an already-running event loop.
        """
        box: dict[str, object] = {}

        def runner():
            try:
                box["result"] = asyncio.run(self._run(system, user))
            except BaseException as exc:  # noqa: BLE001 - re-raised on the caller thread
                box["error"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in box:
            raise box["error"]  # type: ignore[misc]
        return box["result"]  # type: ignore[return-value]

    # ── Public API (matches ClaudeClient) ──────────────────────
    def generate(self, system: str, user: str, max_tokens: int = 4096) -> str:
        # max_tokens is accepted for interface parity; output length is managed
        # by Claude Code in this backend.
        text, _ = self._run_blocking(system, user)
        return text

    def generate_with_usage(
        self, system: str, user: str, max_tokens: int = 4096
    ) -> tuple[str, int]:
        return self._run_blocking(system, user)


def _usage_tokens(usage) -> int:
    """Best-effort total token count from a ResultMessage.usage value."""
    if not usage:
        return 0
    if isinstance(usage, dict):
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
    return int(getattr(usage, "input_tokens", 0)) + int(getattr(usage, "output_tokens", 0))
