"""Screenshot the hero composition at 1920x1080."""
import asyncio
import os

from playwright.async_api import async_playwright

SCRATCH = os.path.dirname(os.path.abspath(__file__))


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1920, "height": 1080}, device_scale_factor=1
        )
        await page.goto("file:///" + os.path.join(SCRATCH, "hero.html").replace("\\", "/"))
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(700)
        await page.screenshot(path=os.path.join(SCRATCH, "reddit_hero.png"))
        await browser.close()
        print("made reddit_hero.png")


asyncio.run(main())
