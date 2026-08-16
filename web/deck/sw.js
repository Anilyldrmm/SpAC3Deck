// web/deck/sw.js
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("fetch", () => {
  // v1: cache-first strateji yok, sadece PWA "add to home screen" icin gerekli minimal SW
});
