const CACHE_NAME = "finance-mvp-shell-v2";
const APP_SHELL = ["./", "manifest.webmanifest", "pwa-icon.svg"];
const API_PREFIXES = ["/api/", "/finance-api/", "/rocket-api/"];

function scopeUrl(path) {
  return new URL(path, self.registration.scope).toString();
}

function isCacheableShellRequest(request) {
  const url = new URL(request.url);
  const scope = new URL(self.registration.scope);

  return (
    request.method === "GET" &&
    url.origin === scope.origin &&
    url.pathname.startsWith(scope.pathname) &&
    !API_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL.map(scopeUrl)))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
      )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (!isCacheableShellRequest(event.request)) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => cached ?? fetch(event.request))
  );
});
