(function () {
    const SNOOZE_KEY = "push-banner-snooze";
    const SYNC_KEY = "push-synced";
    const SNOOZE_MS = 7 * 24 * 60 * 60 * 1000;

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (const cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith(`${name}=`)) {
                return decodeURIComponent(trimmed.slice(name.length + 1));
            }
        }
        return "";
    }

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, "+")
            .replace(/_/g, "/");
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; i += 1) {
            outputArray[i] = rawData.charCodeAt(i);
        }

        return outputArray;
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Request failed.");
        }

        return data;
    }

    function pushSupported() {
        return "serviceWorker" in navigator
            && "PushManager" in window
            && "Notification" in window;
    }

    function snoozed() {
        try {
            const until = Number(localStorage.getItem(SNOOZE_KEY) || 0);
            return until > Date.now();
        } catch (error) {
            return false;
        }
    }

    function setSnooze() {
        try {
            localStorage.setItem(SNOOZE_KEY, String(Date.now() + SNOOZE_MS));
        } catch (error) {
            // Storage can be unavailable in private contexts. Dismiss still hides this page view.
        }
    }

    async function currentSubscription() {
        const registration = await navigator.serviceWorker.ready;
        return registration.pushManager.getSubscription();
    }

    function pushPublicKey() {
        const el = document.querySelector("[data-vapid-public-key]");
        return el ? el.dataset.vapidPublicKey || "" : "";
    }

    function keyMatches(subscription, publicKey) {
        // A subscription made against a previous VAPID key is unusable and will
        // fail on send. Compare the stored applicationServerKey to the current one.
        try {
            const existing = subscription.options && subscription.options.applicationServerKey;
            if (!existing) {
                return false;
            }
            const current = urlBase64ToUint8Array(publicKey);
            const existingBytes = new Uint8Array(existing);
            if (existingBytes.length !== current.length) {
                return false;
            }
            for (let i = 0; i < current.length; i += 1) {
                if (existingBytes[i] !== current[i]) {
                    return false;
                }
            }
            return true;
        } catch (error) {
            return false;
        }
    }

    function subscribeWithKey(registration, publicKey) {
        return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
    }

    async function ensureSubscription(registration, publicKey) {
        let subscription = await registration.pushManager.getSubscription();

        // Drop a subscription left over from an old VAPID key so we can
        // re-register cleanly instead of reusing a dead one.
        if (subscription && !keyMatches(subscription, publicKey)) {
            try {
                await subscription.unsubscribe();
            } catch (error) {
                // Fall through and re-subscribe regardless.
            }
            subscription = null;
        }

        if (subscription) {
            return subscription;
        }

        try {
            return await subscribeWithKey(registration, publicKey);
        } catch (error) {
            // A stale or broken registration can make the first subscribe throw
            // "push service error". Clear anything lingering and retry once so
            // users don't have to manually clear site data.
            const stale = await registration.pushManager.getSubscription();
            if (stale) {
                try {
                    await stale.unsubscribe();
                } catch (unsubError) {
                    // Best effort; retry the subscribe anyway.
                }
            }
            return subscribeWithKey(registration, publicKey);
        }
    }

    function syncStorageKey() {
        const userId = document.body ? document.body.dataset.pushUserId : "";
        return userId ? `${SYNC_KEY}:${userId}` : SYNC_KEY;
    }

    function pushSurfacePresent() {
        return Boolean(document.querySelector("[data-push-controls], [data-push-banner]"));
    }

    async function autoSyncExistingSubscription() {
        if (!pushSurfacePresent() || !pushSupported() || Notification.permission !== "granted") {
            return;
        }

        try {
            const key = syncStorageKey();
            if (sessionStorage.getItem(key)) {
                return;
            }
            sessionStorage.setItem(key, "1");
        } catch (error) {
            // Keep going when storage is unavailable; the POST is idempotent.
        }

        try {
            const registration = await navigator.serviceWorker.ready;
            const publicKey = pushPublicKey();
            let subscription = await registration.pushManager.getSubscription();

            // Silently re-register a subscription bound to an old VAPID key so
            // stuck devices recover on their next visit without clearing data.
            if (publicKey && (!subscription || !keyMatches(subscription, publicKey))) {
                subscription = await ensureSubscription(registration, publicKey);
            }

            if (subscription) {
                await postJson("/push/subscribe/", subscription.toJSON());
            }
        } catch (error) {
            // Auto-heal is best-effort; visible controls will report their own state.
        }
    }

    async function enablePush(publicKey) {
        if (!pushSupported()) {
            return { ok: false, code: "unsupported" };
        }

        if (!publicKey) {
            return { ok: false, code: "missing-key" };
        }

        if (Notification.permission === "denied") {
            return { ok: false, code: "denied" };
        }

        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            return { ok: false, code: permission === "denied" ? "denied" : "dismissed" };
        }

        const registration = await navigator.serviceWorker.ready;
        const subscription = await ensureSubscription(registration, publicKey);

        await postJson("/push/subscribe/", subscription.toJSON());
        return { ok: true, code: "enabled", subscription };
    }

    async function disablePush() {
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
            return;
        }

        const endpoint = subscription.endpoint;
        try {
            await subscription.unsubscribe();
        } catch (error) {
            // Even if the browser-side unsubscribe fails, drop the server record.
        }
        try {
            await postJson("/push/unsubscribe/", { endpoint: endpoint });
        } catch (error) {
            // Best effort; a dead record self-prunes on the next failed send.
        }
    }

    function bindPushControls(root) {
        const publicKey = root.dataset.vapidPublicKey || "";
        const toggleButton = root.querySelector("[data-push-toggle]");
        const testButton = root.querySelector("[data-push-test]");
        const status = root.querySelector("[data-push-status]");

        if (!toggleButton || !testButton || !status) {
            return;
        }

        let busy = false;

        function setStatus(message) {
            status.textContent = message;
        }

        function showEnabled(enabled) {
            toggleButton.textContent = enabled ? "Turn off notifications" : "Enable notifications";
            toggleButton.classList.toggle("btn--primary", !enabled);
            toggleButton.classList.toggle("btn--secondary", enabled);
            testButton.disabled = !enabled;
        }

        async function refreshStatus() {
            await syncPromise;

            if (!pushSupported()) {
                toggleButton.disabled = true;
                testButton.disabled = true;
                setStatus("Push notifications are not supported in this browser.");
                return;
            }

            if (!publicKey) {
                toggleButton.disabled = true;
                testButton.disabled = true;
                setStatus("Push notifications need VAPID keys before they can be enabled.");
                return;
            }

            if (Notification.permission === "denied") {
                toggleButton.disabled = true;
                testButton.disabled = true;
                setStatus("Notifications are blocked for this site.");
                return;
            }

            const subscription = await currentSubscription();
            toggleButton.disabled = false;
            showEnabled(Boolean(subscription));

            if (subscription) {
                setStatus("Notifications are enabled on this device.");
            } else {
                setStatus(`Notifications are off for this device (permission: ${Notification.permission}).`);
            }
        }

        toggleButton.addEventListener("click", async function () {
            if (busy) {
                return;
            }
            busy = true;
            toggleButton.disabled = true;

            const turningOff = Boolean(await currentSubscription());

            try {
                if (turningOff) {
                    setStatus("Turning off notifications...");
                    await disablePush();
                    showEnabled(false);
                    setStatus("Notifications are off for this device.");
                    return;
                }

                setStatus("Requesting notification permission...");
                const result = await enablePush(publicKey);
                if (!result.ok) {
                    showEnabled(false);
                    if (result.code === "denied") {
                        setStatus("Notifications are blocked for this site. Check the site permission and the browser app's notification setting in Android settings.");
                    } else if (result.code === "dismissed") {
                        setStatus("The permission prompt was dismissed without granting. If no prompt appeared, notifications may be disabled for your browser app in Android settings.");
                    } else if (result.code === "missing-key") {
                        setStatus("Push notifications need VAPID keys before they can be enabled.");
                    } else {
                        setStatus("Push notifications are not supported in this browser.");
                    }
                    return;
                }

                showEnabled(true);
                setStatus("Notifications are enabled on this device.");
            } catch (error) {
                setStatus(`Could not update notifications - ${error.name || "Error"}: ${error.message || "unknown"}`);
            } finally {
                busy = false;
                toggleButton.disabled = false;
            }
        });

        testButton.addEventListener("click", async function () {
            testButton.disabled = true;
            setStatus("Sending test notification...");

            try {
                const data = await postJson("/push/test/", {});
                setStatus(`Sent to ${data.sent} ${data.sent === 1 ? "device" : "devices"}.`);
            } catch (error) {
                setStatus(error.message || "Could not send a test notification.");
            } finally {
                testButton.disabled = false;
            }
        });

        refreshStatus().catch(function () {
            setStatus("Could not read notification status.");
        });
    }

    function bindPushBanner(root) {
        const publicKey = root.dataset.vapidPublicKey || "";
        const enableButton = root.querySelector("[data-push-banner-enable]");
        const dismissButton = root.querySelector("[data-push-banner-dismiss]");
        const text = root.querySelector("[data-push-banner-text]");

        if (!enableButton || !dismissButton || !text) {
            return;
        }

        async function maybeShow() {
            await syncPromise;

            if (!pushSupported() || !publicKey || Notification.permission === "denied" || snoozed()) {
                return;
            }

            const subscription = await currentSubscription();
            if (!subscription) {
                root.classList.remove("is-hidden");
            }
        }

        enableButton.addEventListener("click", async function () {
            enableButton.disabled = true;

            try {
                const result = await enablePush(publicKey);
                if (!result.ok) {
                    if (result.code === "denied") {
                        root.classList.add("is-hidden");
                    } else {
                        enableButton.disabled = false;
                    }
                    return;
                }

                text.textContent = "You're set — pings on. ✓";
                enableButton.classList.add("is-hidden");
                dismissButton.classList.add("is-hidden");
                window.setTimeout(function () {
                    root.classList.add("is-hidden");
                }, 2000);
            } catch (error) {
                enableButton.disabled = false;
            }
        });

        dismissButton.addEventListener("click", function () {
            root.classList.add("is-hidden");
            setSnooze();
        });

        maybeShow().catch(function () {
            root.classList.add("is-hidden");
        });
    }

    const syncPromise = autoSyncExistingSubscription();
    document.querySelectorAll("[data-push-controls]").forEach(bindPushControls);
    document.querySelectorAll("[data-push-banner]").forEach(bindPushBanner);
}());
