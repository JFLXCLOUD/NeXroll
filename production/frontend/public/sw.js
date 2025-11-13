 // NeXroll Service Worker for PWA functionality
const CACHE_NAME = 'nexroll-v1.2.1';
const STATIC_CACHE = 'nexroll-static-v1.2.1';
const API_CACHE = 'nexroll-api-v1.2.1';

// Resources to cache immediately on install
const STATIC_ASSETS = [
 '/',
 '/index.html',
 '/manifest.json',
 '/favicon.ico',
 '/NeXroll_Logo_BLK.png',
 '/NeXroll_Logo_WHT.png'
];

// API endpoints to cache for offline viewing
const API_ENDPOINTS = [
  '/health',
  '/system/version',
  '/system/ffmpeg-info',
  '/plex/status',
  '/scheduler/status'
];

// Install event - cache static assets
self.addEventListener('install', event => {
  console.log('[SW] Install event');
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE).then(cache => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      }),
      // Skip waiting to activate immediately
      self.skipWaiting()
    ])
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[SW] Activate event');
  event.waitUntil(
    Promise.all([
      // Clean up old caches
      caches.keys().then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== STATIC_CACHE && cacheName !== API_CACHE && cacheName !== CACHE_NAME) {
              console.log('[SW] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      }),
      // Take control of all clients
      self.clients.claim()
    ])
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Handle API requests
  if (url.pathname.startsWith('/')) {
    // Check if it's an API endpoint we want to cache
    const isApiEndpoint = API_ENDPOINTS.some(endpoint => url.pathname.startsWith(endpoint));

    if (isApiEndpoint && request.method === 'GET') {
      event.respondWith(
        fetch(request)
          .then(response => {
            // Cache successful responses
            if (response.status === 200) {
              const responseClone = response.clone();
              caches.open(API_CACHE).then(cache => {
                cache.put(request, responseClone);
              });
            }
            return response;
          })
          .catch(() => {
            // Return cached version if available
            return caches.match(request).then(cachedResponse => {
              if (cachedResponse) {
                console.log('[SW] Serving cached API response:', url.pathname);
                return cachedResponse;
              }
              // Return offline response for critical endpoints
              if (url.pathname === '/health') {
                return new Response(JSON.stringify({ status: 'offline', cached: true }), {
                  headers: { 'Content-Type': 'application/json' }
                });
              }
              if (url.pathname === '/scheduler/status') {
                return new Response(JSON.stringify({ running: false, cached: true }), {
                  headers: { 'Content-Type': 'application/json' }
                });
              }
              // For other endpoints, return a generic offline message
              return new Response(JSON.stringify({ error: 'Offline', cached: true }), {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
              });
            });
          })
      );
      return;
    }

    // Handle static assets and HTML
    if (request.method === 'GET' && (
      request.destination === 'document' ||
      request.destination === 'script' ||
      request.destination === 'style' ||
      url.pathname.startsWith('/static/')
    )) {
      event.respondWith(
        caches.match(request).then(cachedResponse => {
          if (cachedResponse) {
            return cachedResponse;
          }

          return fetch(request).then(response => {
            // Cache static assets
            if (response.status === 200 && (
              request.destination === 'script' ||
              request.destination === 'style' ||
              url.pathname.startsWith('/static/')
            )) {
              const responseClone = response.clone();
              caches.open(STATIC_CACHE).then(cache => {
                cache.put(request, responseClone);
              });
            }
            return response;
          }).catch(() => {
            // Return cached index.html for navigation requests
            if (request.destination === 'document') {
              return caches.match('/index.html');
            }
          });
        })
      );
      return;
    }
  }

  // Default fetch behavior
  event.respondWith(fetch(request));
});

// Background sync for when connection is restored
self.addEventListener('sync', event => {
  console.log('[SW] Background sync:', event.tag);

  if (event.tag === 'background-sync') {
    event.waitUntil(
      // Refresh cached API data
      Promise.all([
        refreshCache('/health'),
        refreshCache('/system/version'),
        refreshCache('/plex/status'),
        refreshCache('/scheduler/status')
      ])
    );
  }
});

// Message handling for cache updates
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'CACHE_REFRESH') {
    event.waitUntil(
      Promise.all([
        refreshCache('/health'),
        refreshCache('/system/version'),
        refreshCache('/plex/status'),
        refreshCache('/scheduler/status')
      ]).then(() => {
        // Notify client that cache is refreshed
        event.ports[0].postMessage({ type: 'CACHE_REFRESHED' });
      })
    );
  }
});

// Helper function to refresh cached API responses
async function refreshCache(endpoint) {
  try {
    const response = await fetch(endpoint);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      await cache.put(endpoint, response);
      console.log('[SW] Refreshed cache for:', endpoint);
    }
  } catch (error) {
    console.log('[SW] Failed to refresh cache for:', endpoint, error);
  }
}

// Periodic background sync registration hint
self.addEventListener('periodicsync', event => {
  if (event.tag === 'content-sync') {
    event.waitUntil(syncContent());
  }
});

async function syncContent() {
  console.log('[SW] Periodic content sync');
  // Refresh critical API data
  await Promise.all([
    refreshCache('/health'),
    refreshCache('/scheduler/status')
  ]);
}