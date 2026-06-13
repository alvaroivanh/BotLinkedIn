# Claude Agent SDK backend

By default BotLinkedIn talks to Claude through the **Anthropic Messages API**
(`AI_BACKEND=api`). This is the simplest and recommended setup.

As an **optional** alternative, you can route AI generation through the
**Claude Agent SDK** — the same engine that powers the Claude Code CLI — by
setting `AI_BACKEND=agent`. The API-key backend is unchanged and remains the
default; this is purely additive.

## Authentication

The agent backend authenticates Claude Code with **your own Anthropic API key**
(`ANTHROPIC_API_KEY`). The key is passed explicitly to the SDK so usage is billed
to your API account, exactly like the default backend.

> ⚠️ This backend does **not** use a Claude Pro/Max subscription. Anthropic's
> policy prohibits using subscription credentials from third-party tools, so an
> API key is required. If `ANTHROPIC_API_KEY` is missing, the agent backend fails
> fast with a clear error instead of falling back to other credentials.

## Requirements

1. **Claude Code CLI** on your `PATH`:
   ```bash
   npm install -g @anthropic-ai/claude-code
   claude --version
   ```
2. **Python optional deps**:
   ```bash
   pip install -e ".[agent]"
   ```

## Enable it

In your `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
AI_BACKEND=agent
```

That's it — every AI feature (cover letters, reference letters, form answers)
now runs through the Agent SDK. Switch back any time by setting `AI_BACKEND=api`.

## How it works

`src/ai/agent_client.py` exposes `AgentClient`, a drop-in replacement for
`ClaudeClient` with the same `generate()` / `generate_with_usage()` methods.
`get_client()` in `src/ai/client.py` returns it when `AI_BACKEND=agent`.

Because the SDK is async but those methods are called from both sync code and
from inside a running event loop (the Playwright form filler), each call runs the
SDK coroutine in a dedicated worker thread and blocks until it completes.
