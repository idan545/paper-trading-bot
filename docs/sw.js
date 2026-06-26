// Service worker פשוט ל-PWA.
// - app shell נשמר ב-cache (פתיחה מהירה / אופליין).
// - dashboard.json תמיד network-first כדי להציג נתונים טריים, עם נפילה ל-cache.
const SHELL = "paper-shell-v1";
const SHELL_FILES = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // נתונים: network-first
  if (url.pathname.endsWith("dashboard.json")) {
    e.respondWith(
      fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }
  // שאר הקבצים: cache-first
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
