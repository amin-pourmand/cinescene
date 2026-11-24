const CACHE_NAME = "cinescene-pwa-v20261124-startup-v1";
const ASSETS = [
  "./",
  "./index.html",
  "./studio.html",
  "./manifest.webmanifest",
  "./assets/styles.css?v=20261025-reel-v11",
  "./assets/app.js?v=20261124-startup-v1",
  "./assets/intro/workspace-language.js?v=20261124-intro-v9",
  "./assets/intro/index.html",
  "./assets/intro/intro.css?v=20261124-evidence-v1",
  "./assets/intro/intro.js?v=20261124-home-v1",
  "./assets/intro/cinema.webp",
  "./assets/intro/clue.webp",
  "./assets/intro/reel.webp",
  "./assets/intro/evidence.webp",
  "./assets/intro/story-match.webp",
  "./assets/intro/timed-match.webp",
  "./assets/semantic-client.js?v=20261124-text-v1",
  "./assets/semantic-worker.mjs?v=20261124-text-v1",
  "./assets/search-runtime.mjs?v=20261124-text-v1",
  "./assets/hybrid-ranking.mjs?v=20261124-text-v1",
  "./assets/vendor/transformers.min.js",
  "./assets/vendor/ort-wasm-simd-threaded.jsep.mjs",
  "./assets/vendor/ort-wasm-simd-threaded.jsep.wasm",
  "./assets/workspace-ui.js?v=20261123-workflow-v5",
  "./assets/workspace.css?v=20261124-review-v8",
  "./assets/companion-connect.js?v=20261031-companion-v26",
  "./assets/scene-explorer.js?v=20261123-archive-v3",
  "./assets/silent-study/comparison.mp4",
  "./assets/silent-study/frame-early.jpg",
  "./assets/silent-study/frame-late.jpg",
  "./assets/silent-study/report.json",
  "./assets/silent-study/credits.txt",
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
  "./data/catalog-summary.json",
  "./data/release.json"
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

async function freshPage(request, key) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request, {cache: "no-cache"});
    if (response.ok) {
      await cache.put(key, response.clone()).catch(() => {});
      return response;
    }
    return (await cache.match(key)) || response;
  } catch {
    return (await cache.match(key)) || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || event.request.headers.has("range") ||
      url.origin !== self.location.origin || !url.href.startsWith(self.registration.scope)) return;
  const route = url.pathname.slice(new URL(self.registration.scope).pathname.length);
  const page = route || "index.html";
  if (event.request.mode === "navigate" && ["index.html", "studio.html", "assets/intro/index.html"].includes(page)) {
    event.respondWith(freshPage(event.request, `./${page}`));
    return;
  }
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
