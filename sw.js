/* Prayer Room Service Worker
   Purpose: keep all clients in sync and prevent stale UI
   Scope: works correctly for /app deployment
*/

const CACHE_NAME = "prayer-room-pwa-v3";

const CORE = [
  "/",
  "/index.html",
  "/app.html",
  "/styles.css",
  "/app.js",
  "/manifest.webmanifest"
];

// INSTALL: cache core assets and activate immediately
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE))
  );
});

// ACTIVATE: delete ALL old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      )
    )
  );
  self.clients.claim();
});

// FETCH: network-first, cache fallback
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Save a copy for offline use
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, copy);
        });
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
