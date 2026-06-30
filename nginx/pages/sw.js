// sw.js — Service worker CyberBrief (PWA + Web Push)
const CACHE = 'cyberbrief-v2';
const SHELL = [
  '/',
  '/pages/base.css',
  '/pages/icon-192.png',
  '/pages/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
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

// Network-first pour API/rapports, cache-first pour l'app shell
self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  const isDynamic = url.pathname.startsWith('/api/') || url.pathname.startsWith('/reports/');
  if (isDynamic) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
  } else {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
  }
});

// ── Web Push : réception d'une notification ─────────────────────────────────
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) {}
  const title = data.title || 'CyberBrief';
  const options = {
    body:  data.body || 'Nouveau contenu disponible.',
    icon:  '/pages/icon-192.png',
    badge: '/pages/icon-192.png',
    vibrate: [80, 40, 80],
    data:  { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// ── Clic sur la notification → ouvrir le rapport ────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ('focus' in w) { try { w.navigate(target); } catch (_) {} return w.focus(); }
      }
      return clients.openWindow(target);
    })
  );
});
