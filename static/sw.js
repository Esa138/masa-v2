// MASA QUANT — Service Worker
// Handles: PWA caching + Push Notifications

const CACHE_NAME = 'masa-v1';
const OFFLINE_URL = '/app/static/offline.html';

// ── Install: cache offline page ─────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        OFFLINE_URL,
        '/app/static/icon-192.png',
        '/app/static/icon-512.png',
      ]).catch(err => console.warn('[SW] Cache fail:', err));
    })
  );
  self.skipWaiting();
});

// ── Activate: cleanup old caches ────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});

// ── Fetch: network-first, fallback to cache, then offline ───
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  if (!event.request.url.startsWith('http')) return;

  event.respondWith(
    fetch(event.request)
      .catch(() => caches.match(event.request)
        .then(resp => resp || caches.match(OFFLINE_URL)))
  );
});

// ── Push Notifications ──────────────────────────────────────
self.addEventListener('push', (event) => {
  let data = {
    title: 'MASA QUANT',
    body: 'إشارة جديدة!',
    icon: '/app/static/icon-192.png',
    badge: '/app/static/icon-192.png',
    tag: 'masa-default',
    url: '/',
    requireInteraction: false,
  };

  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon,
    badge: data.badge,
    tag: data.tag,
    requireInteraction: data.requireInteraction || false,
    dir: 'rtl',
    lang: 'ar',
    data: { url: data.url || '/' },
    actions: data.actions || [],
    vibrate: [200, 100, 200],
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// ── Notification Click ─────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((windowClients) => {
        // If app already open → focus it
        for (const client of windowClients) {
          if (client.url.includes(self.location.host) && 'focus' in client) {
            client.navigate(targetUrl);
            return client.focus();
          }
        }
        // Otherwise open new window
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
});

// ── Push Subscription Change ────────────────────────────────
self.addEventListener('pushsubscriptionchange', (event) => {
  console.log('[SW] Subscription changed, re-subscribe needed');
});
