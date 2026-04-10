import asyncio
import random


async def random_delay(min_s: float = 1.0, max_s: float = 3.0):
    """Wait a random amount of time to simulate human behavior."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


async def human_type(page, selector: str, text: str):
    """Type text character by character with variable delays like a human."""
    element = page.locator(selector)
    await element.click()
    await asyncio.sleep(random.uniform(0.2, 0.5))

    for char in text:
        await element.press_sequentially(char, delay=random.randint(50, 180))
        if random.random() < 0.05:  # 5% chance of a longer pause (thinking)
            await asyncio.sleep(random.uniform(0.3, 0.8))


async def human_click(page, selector: str):
    """Click an element with a slight random delay before and after."""
    await asyncio.sleep(random.uniform(0.3, 0.8))
    await page.locator(selector).click()
    await asyncio.sleep(random.uniform(0.2, 0.5))


async def random_scroll(page, times: int = 2):
    """Scroll the page randomly to simulate reading."""
    for _ in range(times):
        scroll_amount = random.randint(100, 400)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(1.0, 3.0))


async def hover_random(page):
    """Move mouse to a random position on the page."""
    width = await page.evaluate("window.innerWidth")
    height = await page.evaluate("window.innerHeight")
    x = random.randint(100, max(width - 100, 200))
    y = random.randint(100, max(height - 100, 200))
    await page.mouse.move(x, y)
    await asyncio.sleep(random.uniform(0.5, 1.5))
