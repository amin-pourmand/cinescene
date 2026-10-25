const CACHE_NAME = "cinescene-pwa-v20261025-workspace-v12";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./assets/styles.css?v=20261025-reel-v11",
  "./assets/app.js?v=20261025-workspace-v12",
  "./assets/workspace-ui.js?v=20261025-workspace-v12",
  "./assets/workspace.css?v=20261025-workspace-v12",
  "./assets/scene-explorer.js?v=20261025-reel-v11",
  "./assets/scene-explorer.css?v=20261025-reel-v11",
  "./assets/brand-mark-512.png?v=20261025-reel-v11",
  "./assets/icon.svg?v=20261025-reel-v11",
  "./assets/favicon-32.png?v=20261025-reel-v11",
  "./assets/apple-touch-icon.png?v=20261025-reel-v11",
  "./assets/icon.svg",
  "./assets/icon-192.png",
  "./assets/icon-512.png",
  "./assets/icon-maskable-512.png",
  "./assets/lucide.min.js?v=0.468.0",
  "./assets/manrope-latin.woff2",
  "./assets/vazirmatn-arabic.woff2",
  "./assets/vazirmatn-latin.woff2",
  "./data/catalog.sample.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("cinescene-pwa-") && key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || event.request.headers.has("range") ||
      url.origin !== self.location.origin || !url.href.startsWith(self.registration.scope)) return;
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((response) => {
          if (!response.ok) return response;
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => event.request.mode === "navigate" ? caches.match("./index.html") : Response.error());
    })
  );
});
