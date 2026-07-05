(function () {
    const SNOOZE_KEY = "install-banner-snooze";
    const SNOOZE_MS = 14 * 24 * 60 * 60 * 1000;

    let deferredPrompt = null;

    function isStandalone() {
        return window.matchMedia("(display-mode: standalone)").matches
            || window.navigator.standalone === true;
    }

    function isIOS() {
        const ua = window.navigator.userAgent || "";
        const iOSDevice = /iphone|ipad|ipod/i.test(ua);
        // iPadOS 13+ reports as a Mac; fall back to touch detection.
        const iPadOS = window.navigator.platform === "MacIntel" && window.navigator.maxTouchPoints > 1;
        return iOSDevice || iPadOS;
    }

    function bannerSnoozed() {
        try {
            const until = Number(localStorage.getItem(SNOOZE_KEY) || 0);
            return until > Date.now();
        } catch (error) {
            return false;
        }
    }

    function snoozeBanner() {
        try {
            localStorage.setItem(SNOOZE_KEY, String(Date.now() + SNOOZE_MS));
        } catch (error) {
            // Storage may be unavailable in private contexts.
        }
    }

    function surfaces() {
        return Array.from(document.querySelectorAll("[data-install-surface]"));
    }

    function showSurface(surface) {
        // The dismissible home banner respects snooze; the profile button is persistent.
        if (surface.hasAttribute("data-install-banner") && bannerSnoozed()) {
            return;
        }
        surface.classList.remove("is-hidden");
    }

    function hideAllSurfaces() {
        surfaces().forEach(function (surface) {
            surface.classList.add("is-hidden");
        });
    }

    function revealSurfaces() {
        if (isStandalone()) {
            return;
        }
        surfaces().forEach(showSurface);
    }

    async function triggerNativeInstall(button) {
        if (!deferredPrompt) {
            return false;
        }
        button.disabled = true;
        try {
            deferredPrompt.prompt();
            const choice = await deferredPrompt.userChoice;
            deferredPrompt = null;
            if (choice && choice.outcome === "accepted") {
                hideAllSurfaces();
            } else {
                button.disabled = false;
                snoozeBanner();
            }
        } catch (error) {
            button.disabled = false;
        }
        return true;
    }

    function iosGuideMarkup() {
        const overlay = document.createElement("div");
        overlay.className = "install-guide";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.setAttribute("aria-label", "Install Social Pressure");
        overlay.innerHTML = `
            <div class="install-guide__panel">
                <h2 class="install-guide__title">Add to your Home Screen</h2>
                <ol class="install-guide__steps">
                    <li>
                        <span class="install-guide__glyph" aria-hidden="true">
                            <svg viewBox="0 0 24 24" fill="none"><path d="M12 15V4m0 0 4 4m-4-4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                        </span>
                        <span>Tap the <b>Share</b> button in Safari's toolbar.</span>
                    </li>
                    <li>
                        <span class="install-guide__glyph" aria-hidden="true">
                            <svg viewBox="0 0 24 24" fill="none"><rect x="4" y="4" width="16" height="16" rx="4" stroke="currentColor" stroke-width="2"/><path d="M12 8v8M8 12h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                        </span>
                        <span>Choose <b>Add to Home Screen</b>.</span>
                    </li>
                    <li>
                        <span class="install-guide__glyph" aria-hidden="true">
                            <svg viewBox="0 0 24 24" fill="none"><path d="m5 12 4 4 10-10" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                        </span>
                        <span>Tap <b>Add</b> — you're done.</span>
                    </li>
                </ol>
                <button type="button" class="btn btn--primary btn--full" data-install-guide-close>Got it</button>
            </div>
        `;
        return overlay;
    }

    function openIosGuide() {
        const overlay = iosGuideMarkup();

        function close() {
            document.removeEventListener("keydown", onKey);
            overlay.remove();
        }

        function onKey(event) {
            if (event.key === "Escape") {
                close();
            }
        }

        overlay.querySelector("[data-install-guide-close]").addEventListener("click", close);
        overlay.addEventListener("pointerdown", function (event) {
            if (event.target === overlay) {
                close();
            }
        });
        document.addEventListener("keydown", onKey);
        document.body.append(overlay);
    }

    function bindControls() {
        surfaces().forEach(function (surface) {
            const accept = surface.querySelector("[data-install-accept]");
            const dismiss = surface.querySelector("[data-install-dismiss]");

            if (accept) {
                accept.addEventListener("click", async function () {
                    const handled = await triggerNativeInstall(accept);
                    if (!handled) {
                        openIosGuide();
                    }
                });
            }

            if (dismiss) {
                dismiss.addEventListener("click", function () {
                    surface.classList.add("is-hidden");
                    snoozeBanner();
                });
            }
        });
    }

    if (isStandalone() || !surfaces().length) {
        return;
    }

    bindControls();

    window.addEventListener("beforeinstallprompt", function (event) {
        event.preventDefault();
        deferredPrompt = event;
        revealSurfaces();
    });

    window.addEventListener("appinstalled", function () {
        deferredPrompt = null;
        hideAllSurfaces();
        snoozeBanner();
    });

    // iOS Safari never fires beforeinstallprompt, but the app can still be
    // added manually — surface the prompt with instructions instead.
    if (isIOS()) {
        revealSurfaces();
    }
}());
