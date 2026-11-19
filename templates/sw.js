{% load static %}
const VERSION = 'v2';                       // bump on every deploy
const STATIC_CACHE = 'kwik-static-' + VERSION;

const OFFLINE_URL = "{% url 'offline' %}";

const PRECACHE = [
  OFFLINE_URL,
  "{% static 'icons/icon-192.png' %}",
  "{% static 'icons/icon-512.png' %}",
  "{% static 'pwa.js' %}"
  // add your main css/js here, e.g. "{% static 'css/style.css' %}"
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== STATIC_CACHE).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== 'GET' || url.origin !== self.location.origin) return;

  // Static assets: cache-first
  if (url.pathname.startsWith("{% get_static_prefix %}")) {
    event.respondWith(
      caches.match(req).then((cached) =>
        cached || fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(STATIC_CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
      )
    );
    return;
  }

  // Page navigations: always network. Offline page only if the network fails.
  // (Pages are NOT cached, so logged-in content and CSRF tokens are never stale.)
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => caches.match(OFFLINE_URL))
    );
  }
});