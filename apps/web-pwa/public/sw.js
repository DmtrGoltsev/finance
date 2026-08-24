const CACHE_PREFIX = "finance-mvp-shell-";
const CACHE_NAME = `${CACHE_PREFIX}v3`;
const APP_SHELL = ["./", "manifest.webmanifest", "pwa-icon.svg"];

function scopeUrl(path) {
  return new URL(path, self.registration.scope).toString();
}

function isApiOrOcrRequest(url) {
  return /(^|\/)(?:api|finance-api|rocket-api)(?:\/|$)/.test(url.pathname) ||
    /\/ocr(?:\/|$)/.test(url.pathname);
}

function isCacheableShellRequest(request) {
  const url = new URL(request.url);
  const scope = new URL(self.registration.scope);

  return (
    request.method === "GET" &&
    url.origin === scope.origin &&
    url.pathname.startsWith(scope.pathname) &&
    !isApiOrOcrRequest(url)
  );
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    const fallback = await cache.match(scopeUrl("./"));
    if (fallback) {
      return fallback;
    }
    throw error;
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL.map(scopeUrl)))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (!isCacheableShellRequest(event.request)) {
    return;
  }

  const url = new URL(event.request.url);
  const scope = new URL(self.registration.scope);
  const isNavigation =
    event.request.mode === "navigate" || url.pathname === scope.pathname;
  event.respondWith(isNavigation ? networkFirst(event.request) : cacheFirst(event.request));
});
