"""Render title/end cards as 1080x1920 PNGs via Playwright."""
import asyncio
import os

from playwright.async_api import async_playwright

SCRATCH = os.path.dirname(os.path.abspath(__file__))

END_CARD = """
<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * { margin:0; box-sizing:border-box; }
  body {
    width:1080px; height:1920px; background:#f7f1e7; color:#38332c;
    font-family:'Inter',sans-serif; display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:56px; text-align:center;
    padding:0 90px;
  }
  .brand { font-family:'Fraunces',serif; font-weight:700; font-size:118px; letter-spacing:-2px; }
  .brand span { color:#d9603b; }
  .tag { font-size:44px; line-height:1.45; color:#8a8072; font-weight:500; max-width:820px; }
  .tag b { color:#38332c; }
  .url {
    background:#d9603b; color:#fff; font-weight:700; font-size:40px;
    padding:34px 58px; border-radius:999px; box-shadow:0 10px 28px rgba(217,96,59,.35);
  }
  .foot { font-size:34px; color:#8a8072; font-weight:500; }
  .dots { display:flex; gap:18px; margin-bottom:10px; }
  .dot { width:34px; height:34px; border-radius:50%; }
</style></head><body>
  <div class="dots">
    <div class="dot" style="background:#d9603b"></div>
    <div class="dot" style="background:#d9603b"></div>
    <div class="dot" style="background:#5c7a56"></div>
    <div class="dot" style="border:4px dashed #d9603b"></div>
  </div>
  <div class="brand">Social Pressure<span>.</span></div>
  <div class="tag">Someone <b>seeing</b> you show up beats willpower.<br>No feed, no likes — just your people.</div>
  <div class="url">social-pressure-web.onrender.com</div>
  <div class="foot">Free &middot; runs in your browser &middot; installs like an app</div>
</body></html>
"""

PLACEHOLDER = """
<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700&display=swap" rel="stylesheet">
<style>
  * { margin:0; box-sizing:border-box; }
  body {
    width:1080px; height:1920px; background:#26221d; color:#f7f1e7;
    font-family:'Inter',sans-serif; display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:40px; text-align:center; padding:0 110px;
  }
  .big { font-size:64px; font-weight:700; line-height:1.3; }
  .small { font-size:40px; color:#b6ab99; line-height:1.5; }
</style></head><body>
  <div class="big">[ Your phone screen-recording goes here ]</div>
  <div class="small">Enable notifications &rarr; test ping &rarr; Add to Home Screen</div>
</body></html>
"""


async def shoot(page, html, name):
    await page.set_content(html)
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(600)
    await page.screenshot(path=os.path.join(SCRATCH, name))
    print("made", name)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})
        await shoot(page, END_CARD, "card_end.png")
        await shoot(page, PLACEHOLDER, "card_phone.png")
        await browser.close()


asyncio.run(main())
