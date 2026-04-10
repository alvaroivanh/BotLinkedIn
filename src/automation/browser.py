import logging
from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, Page, async_playwright

from src.config import settings

logger = logging.getLogger(__name__)

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


@asynccontextmanager
async def get_browser_context(
    headless: bool = False,
    storage_state: str | None = None,
):
    """Create a stealth-configured browser context."""
    import random

    async with async_playwright() as p:
        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        launch_args = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        if settings.proxy_url:
            launch_args["proxy"] = {"server": settings.proxy_url}

        browser = await p.chromium.launch(**launch_args)

        context_args = {
            "viewport": viewport,
            "user_agent": user_agent,
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

        if storage_state:
            context_args["storage_state"] = storage_state

        context = await browser.new_context(**context_args)

        # Apply stealth patches
        await _apply_stealth(context)

        try:
            yield context
        finally:
            await context.close()
            await browser.close()


async def _apply_stealth(context: BrowserContext):
    """Apply stealth JavaScript patches to avoid bot detection."""
    await context.add_init_script("""
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', { get: () => false });

        // Override chrome detection
        window.chrome = { runtime: {} };

        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);

        // Override plugins length
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'es'],
        });
    """)


async def new_page(context: BrowserContext) -> Page:
    """Create a new page in the context."""
    page = await context.new_page()
    page.set_default_timeout(30000)
    return page
