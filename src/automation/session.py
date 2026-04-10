import json
import logging
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


def get_session_path(platform: str) -> Path:
    return settings.sessions_dir / f"{platform}_state.json"


async def save_session(context, platform: str):
    """Save browser session state (cookies, localStorage) to disk."""
    path = get_session_path(platform)
    state = await context.storage_state()
    path.write_text(json.dumps(state, indent=2))
    logger.info(f"Session saved for {platform}")


def load_session_path(platform: str) -> str | None:
    """Get the session file path if it exists and is valid."""
    path = get_session_path(platform)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if data.get("cookies"):
                logger.info(f"Found existing session for {platform}")
                return str(path)
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"Invalid session file for {platform}, will create new session")
    return None


async def login_linkedin(page):
    """Perform LinkedIn login interactively."""
    await page.goto("https://www.linkedin.com/login")
    await page.wait_for_load_state("networkidle")

    # Fill email
    email_field = page.locator("#username")
    await email_field.fill(settings.linkedin_email)

    # Fill password
    password_field = page.locator("#password")
    await password_field.fill(settings.linkedin_password)

    # Click sign in
    await page.locator('button[type="submit"]').click()

    # Wait for login to complete (user may need to handle 2FA manually)
    try:
        await page.wait_for_url("**/feed/**", timeout=60000)
        logger.info("LinkedIn login successful")
    except Exception:
        logger.info("Waiting for manual 2FA completion...")
        await page.wait_for_url("**/feed/**", timeout=120000)
        logger.info("LinkedIn login completed after 2FA")


async def verify_linkedin_session(page) -> bool:
    """Check if the current LinkedIn session is still valid."""
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        # If we're redirected to login, session is invalid
        if "/login" in page.url or "/authwall" in page.url:
            return False
        return True
    except Exception:
        return False
