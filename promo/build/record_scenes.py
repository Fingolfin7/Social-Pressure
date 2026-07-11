"""Record all app-flow clips for the promo video.

Renders at true 1080x1920 by zooming the page 2.667x (layout equals a 405px
phone), so text is crisp in the recorded video. Each scene is its own browser
context / video file. Timeline marks are printed for trimming.
"""
import asyncio
import json
import os
import time

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8765"
PASSWORD = "demo-pass-1234"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(SCRATCH, "clips")
os.makedirs(CLIPS, exist_ok=True)

ZOOM = "2.667"

INIT_JS = """
(() => {
  const applyZoom = () => {
    if (document.documentElement) document.documentElement.style.zoom = '__ZOOM__';
  };
  applyZoom();
  document.addEventListener('DOMContentLoaded', applyZoom);

  window.__ripple = (x, y) => {
    if (!document.body) return;
    const d = document.createElement('div');
    d.style.cssText = `position:fixed;left:${x - 21}px;top:${y - 21}px;` +
      'width:42px;height:42px;border-radius:50%;background:rgba(40,35,30,0.25);' +
      'border:2.5px solid rgba(255,255,255,0.9);pointer-events:none;z-index:99999;' +
      'box-shadow:0 2px 10px rgba(0,0,0,0.2);' +
      'transform:scale(0.45);opacity:1;transition:transform .4s ease-out,opacity .4s ease-out;';
    document.body.appendChild(d);
    requestAnimationFrame(() => {
      d.style.transform = 'scale(1.35)';
      d.style.opacity = '0';
    });
    setTimeout(() => d.remove(), 460);
  };
})();
""".replace("__ZOOM__", ZOOM)

marks = {}


class Scene:
    def __init__(self, name):
        self.name = name
        self.t0 = None
        marks[name] = []

    def start(self):
        self.t0 = time.monotonic()

    def mark(self, label):
        marks[self.name].append((round(time.monotonic() - self.t0, 2), label))


async def new_ctx(browser, video_name=None):
    kwargs = dict(
        viewport={"width": 1080, "height": 1920},
        device_scale_factor=1,
        is_mobile=True,
        has_touch=True,
        permissions=["clipboard-write", "clipboard-read", "notifications"],
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
        ),
    )
    if video_name:
        kwargs["record_video_dir"] = os.path.join(SCRATCH, "raw_" + video_name)
        kwargs["record_video_size"] = {"width": 1080, "height": 1920}
    ctx = await browser.new_context(**kwargs)
    await ctx.add_init_script(INIT_JS)
    return ctx


async def login_state(browser, username):
    """Log in without video, return storage_state dict."""
    ctx = await browser.new_context()
    page = await ctx.new_page()
    await page.goto(f"{BASE}/users/login/")
    await page.fill("input[name=username]", username)
    await page.fill("input[name=password]", PASSWORD)
    await page.click("button[type=submit]")
    await page.wait_for_url(f"{BASE}/**")
    await page.wait_for_load_state("networkidle")
    state = await ctx.storage_state()
    await ctx.close()
    return state


async def open_scene(browser, name, storage_state):
    ctx = await browser.new_context(
        storage_state=storage_state,
        viewport={"width": 1080, "height": 1920},
        device_scale_factor=1,
        is_mobile=True,
        has_touch=True,
        permissions=["clipboard-write", "clipboard-read", "notifications"],
        record_video_dir=os.path.join(SCRATCH, "raw_" + name),
        record_video_size={"width": 1080, "height": 1920},
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
        ),
    )
    await ctx.add_init_script(INIT_JS)
    page = await ctx.new_page()
    return ctx, page


async def save_video(ctx, page, name):
    video = page.video
    await ctx.close()
    path = await video.path()
    dest = os.path.join(CLIPS, f"{name}.webm")
    if os.path.exists(dest):
        os.remove(dest)
    os.replace(path, dest)
    return dest


async def tap(page, selector):
    """Show a tap ripple at the element's center, then dispatch a JS click.

    Avoids real mouse coordinates entirely — mobile emulation plus CSS zoom
    makes coordinate spaces unreliable, while DOM clicks are deterministic.
    """
    state = await page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el) return 'missing';
          const r = el.getBoundingClientRect();
          if (r.top < 0 || r.bottom > window.innerHeight) {
            el.scrollIntoView({block: 'center', behavior: 'smooth'});
            return 'scrolled';
          }
          return 'ok';
        }""",
        selector,
    )
    if state == "missing":
        raise RuntimeError(f"tap: no element for {selector}")
    if state == "scrolled":
        await page.wait_for_timeout(800)
    await page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          const r = el.getBoundingClientRect();
          if (window.__ripple) window.__ripple(r.x + r.width / 2, r.y + r.height / 2);
          setTimeout(() => el.click(), 130);
        }""",
        selector,
    )
    await page.wait_for_timeout(320)


async def smooth_scroll(page, amount, duration_ms=700):
    await page.evaluate(
        "([amount]) => window.scrollBy({top: amount, behavior: 'smooth'})", [amount]
    )
    await page.wait_for_timeout(duration_ms)


async def scene_hook(browser, alex_state):
    s = Scene("hook")
    ctx, page = await open_scene(browser, "hook", alex_state)
    s.start()
    await page.goto(f"{BASE}/projects/1/")
    await page.wait_for_load_state("networkidle")
    s.mark("loaded")
    await page.wait_for_timeout(2000)
    s.mark("scroll1")
    await smooth_scroll(page, 340, 900)
    await page.wait_for_timeout(900)
    s.mark("scroll2")
    await smooth_scroll(page, 320, 900)
    await page.wait_for_timeout(1800)
    s.mark("end")
    return await save_video(ctx, page, "hook")


async def scene_create_invite(browser, alexj_state):
    s = Scene("create")
    ctx, page = await open_scene(browser, "create", alexj_state)
    s.start()
    await page.goto(f"{BASE}/projects/new/")
    await page.wait_for_load_state("networkidle")
    s.mark("loaded")
    await page.wait_for_timeout(1400)
    await tap(page, "input[value=gym] + .template-picker__card")
    s.mark("template")
    await page.wait_for_timeout(1300)
    await smooth_scroll(page, 380, 800)
    await page.wait_for_timeout(1000)
    s.mark("recap-visible")
    await smooth_scroll(page, 260, 700)
    await page.wait_for_timeout(900)
    await tap(page, "form button[type=submit]")
    await page.wait_for_url("**/target/**")
    await page.wait_for_load_state("networkidle")
    s.mark("target-page")
    await page.wait_for_timeout(1300)
    await tap(page, "[data-stepper-plus]")
    s.mark("stepper-plus")
    await page.wait_for_timeout(1000)
    await tap(page, "form button[type=submit]")
    await page.wait_for_load_state("networkidle")
    s.mark("project-page")
    project_url = page.url
    await page.wait_for_timeout(1500)
    s.mark("scroll-to-invite")
    await smooth_scroll(page, 420, 900)
    await page.wait_for_timeout(900)
    copy_btn = page.locator("[data-copy]").first
    invite_url = await copy_btn.get_attribute("data-copy-text")
    s.mark("copy")
    await tap(page, "[data-copy]")
    await page.wait_for_timeout(1800)
    s.mark("end")
    path = await save_video(ctx, page, "create")
    return path, invite_url, project_url


async def scene_join(browser, maya_state, invite_url):
    s = Scene("join")
    ctx, page = await open_scene(browser, "join", maya_state)
    s.start()
    await page.goto(invite_url)
    await page.wait_for_load_state("networkidle")
    s.mark("loaded")
    await page.wait_for_timeout(2200)
    await smooth_scroll(page, 420, 900)
    await page.wait_for_timeout(1100)
    s.mark("stepper")
    await tap(page, "[data-stepper-minus]")
    await page.wait_for_timeout(1100)
    s.mark("join-click")
    await tap(page, ".join-form button[type=submit]")
    await page.wait_for_load_state("networkidle")
    s.mark("project-page")
    await page.wait_for_timeout(2400)
    s.mark("end")
    return await save_video(ctx, page, "join")


async def scene_log_and_partner(browser, alex_state, maya_state):
    """Record Alex logging and Maya's phone receiving it, simultaneously."""
    sa = Scene("log")
    sm = Scene("partner")
    ctx_a, page_a = await open_scene(browser, "log", alex_state)
    ctx_m, page_m = await open_scene(browser, "partner", maya_state)
    sa.start()
    sm.start()

    # Maya settles on the project screen, scrolled to see the feed top.
    await page_m.goto(f"{BASE}/projects/1/")
    await page_m.wait_for_load_state("networkidle")
    sm.mark("loaded")
    await smooth_scroll(page_m, 560, 900)
    n_items = await page_m.evaluate("document.querySelectorAll('.feed-item').length")

    # Alex logs his session.
    await page_a.goto(f"{BASE}/projects/1/")
    await page_a.wait_for_load_state("networkidle")
    sa.mark("loaded")
    await page_a.wait_for_timeout(1600)
    sa.mark("tap-log")
    await tap(page_a, ".log-action")
    await page_a.wait_for_url("**/log/**")
    await page_a.wait_for_load_state("networkidle")
    sa.mark("log-page")
    await page_a.wait_for_timeout(1700)
    sa.mark("tap-circle")
    await tap(page_a, ".log-circle")
    await page_a.wait_for_url("**/logged/**")
    await page_a.wait_for_load_state("networkidle")
    sa.mark("logged-page")
    await page_a.wait_for_timeout(2200)
    sa.mark("see-project")
    await tap(page_a, "a.btn--primary")
    await page_a.wait_for_load_state("networkidle")
    sa.mark("project-updated")
    await page_a.wait_for_timeout(2200)
    sa.mark("end")

    # Maya's screen picks the event up via the live poll (<=10s).
    sm.mark("waiting-update")
    await page_m.wait_for_function(
        "n => document.querySelectorAll('.feed-item').length > n",
        arg=n_items,
        timeout=25000,
    )
    sm.mark("feed-updated")
    await page_m.wait_for_timeout(1800)

    # React to the newest event.
    add_btn = page_m.locator(".feed-item [data-reaction-add]").first
    sm.mark("tap-add-reaction")
    await tap(page_m, ".feed-item [data-reaction-add]")
    await page_m.wait_for_selector("[data-reaction-picker] [data-emoji]")
    await page_m.wait_for_timeout(900)
    sm.mark("pick-fire")
    await tap(page_m, "[data-reaction-picker] [data-emoji='\N{FIRE}']")
    await page_m.wait_for_timeout(1600)

    # Nudge.
    sm.mark("nudge")
    await tap(page_m, "[data-nudge]")
    await page_m.wait_for_timeout(2000)
    sm.mark("end")

    path_a = await save_video(ctx_a, page_a, "log")
    path_m = await save_video(ctx_m, page_m, "partner")
    return path_a, path_m


async def scene_push(browser, alex_state):
    s = Scene("push")
    ctx, page = await open_scene(browser, "push", alex_state)
    s.start()
    await page.goto(f"{BASE}/projects/1/")
    await page.wait_for_load_state("networkidle")
    s.mark("loaded")
    await page.wait_for_timeout(2500)
    banner = page.locator("[data-push-banner]")
    visible = await banner.is_visible()
    s.mark(f"banner-visible={visible}")
    if visible:
        await page.wait_for_timeout(800)
        s.mark("tap-enable")
        await tap(page, "[data-push-banner-enable]")
        await page.wait_for_timeout(2500)
    s.mark("end")
    return await save_video(ctx, page, "push")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        alex_state = await login_state(browser, "alex")
        maya_state = await login_state(browser, "maya")
        alexj_state = await login_state(browser, "alexj")

        print("hook:", await scene_hook(browser, alex_state))
        create_path, invite_url, project_url = await scene_create_invite(
            browser, alexj_state
        )
        print("create:", create_path, "| invite:", invite_url)
        print("join:", await scene_join(browser, maya_state, invite_url))
        log_path, partner_path = await scene_log_and_partner(
            browser, alex_state, maya_state
        )
        print("log:", log_path)
        print("partner:", partner_path)
        print("push:", await scene_push(browser, alex_state))

        await browser.close()

    with open(os.path.join(SCRATCH, "marks.json"), "w", encoding="utf-8") as f:
        json.dump(marks, f, indent=2, ensure_ascii=False)
    print(json.dumps(marks, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
