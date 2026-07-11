"""Re-record the push-banner beat: force-show the app's banner, ripple on Enable."""
import asyncio

from playwright.async_api import async_playwright

from record_scenes import BASE, Scene, login_state, open_scene, save_video, marks


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        alex_state = await login_state(browser, "alex")
        s = Scene("push")
        ctx, page = await open_scene(browser, "push", alex_state)
        s.start()
        await page.goto(f"{BASE}/projects/1/")
        await page.wait_for_load_state("networkidle")
        s.mark("loaded")
        await page.wait_for_timeout(1200)
        await page.evaluate(
            """() => {
              const b = document.querySelector('[data-push-banner]');
              b.classList.remove('is-hidden');
              b.scrollIntoView({block: 'center', behavior: 'smooth'});
            }"""
        )
        s.mark("banner-shown")
        await page.wait_for_timeout(2000)
        await page.evaluate(
            """() => {
              const el = document.querySelector('[data-push-banner-enable]');
              const r = el.getBoundingClientRect();
              window.__ripple(r.x + r.width / 2, r.y + r.height / 2);
            }"""
        )
        s.mark("tap-enable")
        await page.wait_for_timeout(1200)
        s.mark("end")
        print("push:", await save_video(ctx, page, "push"))
        print(marks["push"])
        await browser.close()


asyncio.run(main())
