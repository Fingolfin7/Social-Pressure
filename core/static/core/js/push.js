(function () {
    const root = document.querySelector("[data-push-controls]");
    if (!root) {
        return;
    }

    const publicKey = root.dataset.vapidPublicKey || "";
    const enableButton = root.querySelector("[data-push-enable]");
    const testButton = root.querySelector("[data-push-test]");
    const status = root.querySelector("[data-push-status]");

    function setStatus(message) {
        status.textContent = message;
    }

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

    async function refreshStatus() {
        if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
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

        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();

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
            const permission = await Notification.requestPermission();
            if (permission !== "granted") {
                enableButton.disabled = false;
                setStatus(permission === "denied"
                    ? "Notifications are blocked for this site. Check the site permission and the browser app's notification setting in Android settings."
                    : "The permission prompt was dismissed without granting. If no prompt appeared, notifications may be disabled for your browser app in Android settings.");
                return;
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
            testButton.disabled = false;
            setStatus("Notifications are enabled on this device.");
        } catch (error) {
            enableButton.disabled = false;
            setStatus(`Could not enable notifications — ${error.name || "Error"}: ${error.message || "unknown"}`);
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
}());
