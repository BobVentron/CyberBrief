// sw.js — Service worker CyberBrief (PWA)
// Minimal : requis pour l'installabilite + cache de l'app shell.
const CACHE = 'cyberbrief-v1';
const SHELL = [
  '/',
  '/pages/base.css',
  '/pages/icon-192.png',
  '/pages/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first pour les rapports/API, cache-first pour l'app shell.
self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const isApi = url.pathname.startsWith('/api/') || url.pathname.startsWith('/reports/');

  if (isApi) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
  } else {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
  }
});
