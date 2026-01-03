const CACHE_NAME = "prayer-room-pwa-v1";
const CORE = ["./","./index.html","./styles.css","./app.js","./sw.js","./manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE_NAME);
    await c.addAll(CORE);
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => (k === CACHE_NAME ? null : caches.delete(k))));
    self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith((async () => {
    const cached = await caches.match(e.request);
    if (cached) return cached;
    try {
      const res = await fetch(e.request);
      const url = new URL(e.request.url);
      if (url.origin === self.location.origin) {
        const c = await caches.open(CACHE_NAME);
        c.put(e.request, res.clone());
      }
      return res;
    } catch {
      return (await caches.match("./index.html")) || new Response("Offline", { status: 503 });
    }
  })());
});
