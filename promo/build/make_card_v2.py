"""Render the v2 end card with the test-user CTA."""
import asyncio
import os

from playwright.async_api import async_playwright

SCRATCH = os.path.dirname(os.path.abspath(__file__))

CARD = """
<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * { margin:0; box-sizing:border-box; }
  body {
    width:1080px; height:1920px; background:#f7f1e7; color:#38332c;
    font-family:'Inter',sans-serif; display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:52px; text-align:center;
    padding:0 90px;
  }
  .brand { font-family:'Fraunces',serif; font-weight:700; font-size:104px; letter-spacing:-2px; }
  .brand span { color:#d9603b; }
  .cta { font-family:'Fraunces',serif; font-weight:600; font-size:66px; color:#d9603b; line-height:1.25; }
  .tag { font-size:42px; line-height:1.5; color:#8a8072; font-weight:500; max-width:840px; }
  .tag b { color:#38332c; }
  .url {
    background:#d9603b; color:#fff; font-weight:700; font-size:40px;
    padding:34px 58px; border-radius:999px; box-shadow:0 10px 28px rgba(217,96,59,.35);
  }
  .foot { font-size:34px; color:#8a8072; font-weight:500; }
  .dots { display:flex; gap:18px; margin-bottom:6px; }
  .dot { width:34px; height:34px; border-radius:50%; }
</style></head><body>
  <div class="dots">
    <div class="dot" style="background:#d9603b"></div>
    <div class="dot" style="background:#d9603b"></div>
    <div class="dot" style="background:#5c7a56"></div>
    <div class="dot" style="border:4px dashed #d9603b"></div>
  </div>
  <div class="brand">Social Pressure<span>.</span></div>
  <div class="cta">Looking for a few<br>test users.</div>
  <div class="tag">Grab someone who'll <b>notice</b> when you show up<br>— and hold each other to it.</div>
  <div class="url">social-pressure-web.onrender.com</div>
  <div class="foot">Free &middot; runs in your browser &middot; installs like an app</div>
</body></html>
"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})
        await page.set_content(CARD)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(600)
        await page.screenshot(path=os.path.join(SCRATCH, "card_end_v2.png"))
        await browser.close()
        print("made card_end_v2.png")


asyncio.run(main())
