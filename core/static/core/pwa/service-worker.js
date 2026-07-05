const CACHE_PREFIX = "social-pressure-pwa";
const PRECACHE = `${CACHE_PREFIX}-precache-v1`;
const OFFLINE_URL = "/offline/";
const ICON_URL = "/static/core/images/icons/social-pressure-icon-192.png";

const PRECACHE_URLS = [
    OFFLINE_URL,
];

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(PRECACHE).then(function (cache) {
            return cache.addAll(PRECACHE_URLS);
        })
    );
    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (cacheNames) {
            return Promise.all(
                cacheNames
                    .filter(function (cacheName) {
                        return cacheName.startsWith(CACHE_PREFIX)
                            && cacheName !== PRECACHE;
                    })
                    .map(function (cacheName) {
                        return caches.delete(cacheName);
                    })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener("fetch", function (event) {
    if (event.request.method !== "GET") {
        return;
    }

    const requestUrl = new URL(event.request.url);
    if (requestUrl.origin !== self.location.origin) {
        return;
    }

    if (event.request.mode === "navigate") {
        event.respondWith(
            fetch(event.request).catch(function () {
                return caches.match(OFFLINE_URL);
            })
        );
    }
});

self.addEventListener("push", function (event) {
    let payload = {};

    if (event.data) {
        try {
            payload = event.data.json();
        } catch (error) {
            payload = {
                title: "Social Pressure",
                body: event.data.text(),
                url: "/",
            };
        }
    }

    const title = payload.title || "Social Pressure";
    const options = {
        body: payload.body || "",
        icon: ICON_URL,
        data: {
            url: payload.url || "/",
        },
    };

    event.waitUntil(
        Promise.all([
            self.registration.showNotification(title, options),
            self.clients.matchAll({ type: "window" }).then(function (clientList) {
                clientList.forEach(function (client) {
                    client.postMessage({ type: "refresh" });
                });
            }),
        ])
    );
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();

    const url = event.notification.data && event.notification.data.url
        ? event.notification.data.url
        : "/";
    const targetUrl = new URL(url, self.location.origin).href;

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clientList) {
            for (const client of clientList) {
                if (client.url === targetUrl && "focus" in client) {
                    return client.focus();
                }
            }

            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
