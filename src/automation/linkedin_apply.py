import logging
from pathlib import Path

from src.automation.browser import get_browser_context, new_page
from src.automation.form_filler import fill_form_fields
from src.automation.humanize import human_click, random_delay, random_scroll
from src.automation.session import load_session_path, login_linkedin, save_session, verify_linkedin_session
from src.config import settings
from src.cv.models import ResumeData

logger = logging.getLogger(__name__)


async def apply_to_job(
    job_url: str,
    resume: ResumeData,
    resume_pdf_path: str,
    headless: bool = False,
) -> dict:
    """Apply to a LinkedIn job using Easy Apply.

    Returns a dict with: success (bool), message (str), screenshot (str|None)
    """
    storage_state = load_session_path("linkedin")

    async with get_browser_context(headless=headless, storage_state=storage_state) as context:
        page = await new_page(context)

        # Verify session or login
        if not await verify_linkedin_session(page):
            logger.info("Session expired, logging in...")
            await login_linkedin(page)
            await save_session(context, "linkedin")

        # Navigate to job
        await page.goto(job_url, wait_until="domcontentloaded")
        await random_delay(2, 4)
        await random_scroll(page, times=1)

        # Look for Easy Apply button
        easy_apply_btn = page.locator("button.jobs-apply-button").first
        if not await easy_apply_btn.is_visible():
            return {
                "success": False,
                "message": "Easy Apply button not found. May require external application.",
                "screenshot": None,
            }

        await human_click(page, "button.jobs-apply-button")
        await random_delay(1, 2)

        # Step through the Easy Apply modal
        max_steps = 10
        for step in range(max_steps):
            logger.info(f"Easy Apply step {step + 1}")

            # Check if we're done (success screen)
            success_indicator = page.locator("div.artdeco-inline-feedback--success, h2:has-text('application was sent')")
            if await success_indicator.count() > 0:
                await save_session(context, "linkedin")
                return {
                    "success": True,
                    "message": "Application submitted successfully!",
                    "screenshot": None,
                }

            # Upload resume if file input is visible
            file_input = page.locator('input[type="file"]')
            if await file_input.count() > 0:
                try:
                    await file_input.set_input_files(resume_pdf_path)
                    logger.info("Resume uploaded")
                    await random_delay(1, 2)
                except Exception as e:
                    logger.warning(f"Error uploading resume: {e}")

            # Fill form fields on this step
            await fill_form_fields(page, resume)
            await random_delay(0.5, 1.5)

            # Look for Next/Review/Submit button
            next_btn = page.locator(
                "button[aria-label='Continue to next step'], "
                "button[aria-label='Review your application'], "
                "button[aria-label='Submit application'], "
                "button:has-text('Next'), "
                "button:has-text('Review'), "
                "button:has-text('Submit application')"
            ).first

            if await next_btn.is_visible():
                button_text = await next_btn.inner_text()
                logger.info(f"Clicking: {button_text}")
                await human_click(page, next_btn)
                await random_delay(1, 3)
            else:
                # Try to find any primary button
                primary_btn = page.locator("button.artdeco-button--primary").first
                if await primary_btn.is_visible():
                    await human_click(page, primary_btn)
                    await random_delay(1, 3)
                else:
                    logger.warning("No navigation button found")
                    break

        # Take screenshot of final state
        screenshot_path = str(settings.sessions_dir / "last_apply_screenshot.png")
        await page.screenshot(path=screenshot_path)
        await save_session(context, "linkedin")

        return {
            "success": False,
            "message": "Application flow did not complete within expected steps",
            "screenshot": screenshot_path,
        }


async def apply_batch(
    job_urls: list[str],
    resume: ResumeData,
    resume_pdf_path: str,
    headless: bool = False,
    max_applications: int | None = None,
) -> list[dict]:
    """Apply to multiple jobs with delays between applications."""
    import random

    results = []
    limit = max_applications or settings.applications_per_session

    for i, url in enumerate(job_urls[:limit]):
        logger.info(f"Applying to job {i + 1}/{min(len(job_urls), limit)}: {url}")

        result = await apply_to_job(url, resume, resume_pdf_path, headless)
        result["url"] = url
        results.append(result)

        if result["success"]:
            logger.info(f"Successfully applied to job {i + 1}")
        else:
            logger.warning(f"Failed to apply to job {i + 1}: {result['message']}")

        # Delay between applications
        if i < len(job_urls) - 1:
            delay = random.uniform(settings.delay_min, settings.delay_max)
            logger.info(f"Waiting {delay:.0f}s before next application...")
            import asyncio
            await asyncio.sleep(delay)

    return results
