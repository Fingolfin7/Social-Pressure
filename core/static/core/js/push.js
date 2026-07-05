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
            const subscription = await currentSubscription();
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
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });
        }

        await postJson("/push/subscribe/", subscription.toJSON());
        return { ok: true, code: "enabled", subscription };
    }

    function bindPushControls(root) {
        const publicKey = root.dataset.vapidPublicKey || "";
        const enableButton = root.querySelector("[data-push-enable]");
        const testButton = root.querySelector("[data-push-test]");
        const status = root.querySelector("[data-push-status]");

        if (!enableButton || !testButton || !status) {
            return;
        }

        function setStatus(message) {
            status.textContent = message;
        }

        async function refreshStatus() {
            await syncPromise;

            if (!pushSupported()) {
                enableButton.disabled = true;
                testButton.disabled = true;
                setStatus("Push notifications are not supported in this browser.");
                return;
            }

            if (!publicKey) {
                enableButton.disabled = true;
                testButton.disabled = true;
                setStatus("Push notifications need VAPID keys before they can be enabled.");
                return;
            }

            if (Notification.permission === "denied") {
                enableButton.disabled = true;
                testButton.disabled = true;
                setStatus("Notifications are blocked for this site.");
                return;
            }

            const subscription = await currentSubscription();

            if (subscription) {
                enableButton.disabled = true;
                testButton.disabled = false;
                setStatus("Notifications are enabled on this device.");
            } else {
                enableButton.disabled = false;
                testButton.disabled = true;
                setStatus(`Notifications are off for this device (permission: ${Notification.permission}).`);
            }
        }

        enableButton.addEventListener("click", async function () {
            enableButton.disabled = true;
            setStatus("Requesting notification permission...");

            try {
                const result = await enablePush(publicKey);
                if (!result.ok) {
                    enableButton.disabled = false;
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

                testButton.disabled = false;
                setStatus("Notifications are enabled on this device.");
            } catch (error) {
                enableButton.disabled = false;
                setStatus(`Could not enable notifications - ${error.name || "Error"}: ${error.message || "unknown"}`);
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
