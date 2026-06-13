import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import settings


class ClaudeClient:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
    )
    def generate(self, system: str, user: str, max_tokens: int = 4096) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    def generate_with_usage(self, system: str, user: str, max_tokens: int = 4096) -> tuple[str, int]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        return response.content[0].text, total_tokens


_client: "ClaudeClient | AgentClient | None" = None


def get_client() -> "ClaudeClient | AgentClient":
    global _client
    if _client is None:
        if settings.ai_backend == "agent":
            # Lazy import so the api backend never needs the Agent SDK installed.
            from src.ai.agent_client import AgentClient

            _client = AgentClient()
        else:
            _client = ClaudeClient()
    return _client
