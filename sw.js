// Keeps the game working offline once it's installed.
// Every time you're online it checks the server for a newer version first
// (so updates arrive right away); only when offline does it use the saved copy.
// Requests to other sites (the leaderboard database) are left alone.
const CACHE = "lords-v4";
const FILES = ["./", "index.html", "privacy.html", "manifest.webmanifest", "icon-180.png", "icon-192.png", "icon-512.png", "fonts/cinzel.woff2", "fonts/eb-garamond.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES.map((f) => new Request(f, { cache: "reload" })))));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request, { cache: "no-cache" })
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
