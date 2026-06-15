from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    # AI backend: "api" (direct Messages API, default), "agent" (Claude Agent SDK),
    # or "openrouter" (OpenAI-compatible OpenRouter, e.g. Gemini Flash).
    ai_backend: str = "api"

    # OpenRouter (used when ai_backend == "openrouter")
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.5-flash-lite"

    # LinkedIn
    linkedin_email: str = ""
    linkedin_password: str = ""

    # Job search
    # Country hint for Indeed/Glassdoor scraping via python-jobspy.
    search_country: str = "colombia"

    # Application limits
    max_daily_applications: int = 50
    delay_min: int = 5
    delay_max: int = 15
    applications_per_session: int = 20

    # Proxy
    proxy_url: str = ""

    # Database
    database_url: str = f"sqlite:///{DATA_DIR / 'botlinkedin.db'}"

    # Dashboard
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000

    # Logging
    log_level: str = "INFO"

    @property
    def resumes_dir(self) -> Path:
        path = DATA_DIR / "resumes"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def letters_dir(self) -> Path:
        path = DATA_DIR / "letters"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def sessions_dir(self) -> Path:
        path = DATA_DIR / "sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
