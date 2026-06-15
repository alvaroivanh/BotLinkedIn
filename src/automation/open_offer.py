"""Open a job-offer URL in a fresh, headed Chromium window via Playwright.

Some portals (e.g. Computrabajo) block the user's main browser session with an
anti-bot 403, while a clean browser profile loads fine. This launches a
Playwright-controlled Chromium with a fresh context (no cookies, no extensions)
pointed at the offer, so the user can review and apply there.

Run as a standalone, detached process:
    python -m src.automation.open_offer <url>

The window stays open until the user closes it.
"""

import sys
import time


def open_offer(url: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport=None,  # use the real window size
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass  # leave the window open even if navigation is slow/partial
        # Keep the process alive until the user closes the browser window.
        try:
            while browser.is_connected():
                time.sleep(1)
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        open_offer(sys.argv[1])
