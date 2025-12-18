/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

declare const self: ServiceWorkerGlobalScope;

import { files, version } from '$service-worker';

const CACHE_NAME = `cache-${version}`;

// Only cache static files that are safe (images, fonts, icons)
// EXCLUDE: JS, CSS, HTML - these should always be fresh to prevent stale code
const SAFE_TO_CACHE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.otf'];

const CACHEABLE_ASSETS = files.filter((file) =>
    SAFE_TO_CACHE_EXTENSIONS.some((ext) => file.toLowerCase().endsWith(ext))
);

// Install: cache only safe static assets (images, fonts)
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches
            .open(CACHE_NAME)
            .then((cache) => cache.addAll(CACHEABLE_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate: clean up old caches immediately
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((keys) =>
                Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
            )
            .then(() => self.clients.claim())
    );
});

// Fetch handler: only serve cached images/fonts, everything else goes to network
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // Skip cross-origin requests
    if (url.origin !== location.origin) return;

    // Skip API calls
    if (url.pathname.startsWith('/api')) return;

    // Only use cache for safe static assets (images, fonts)
    const isSafeToCache = SAFE_TO_CACHE_EXTENSIONS.some((ext) =>
        url.pathname.toLowerCase().endsWith(ext)
    );

    if (!isSafeToCache) {
        // JS, CSS, HTML - always go to network, never cache
        return;
    }

    // Images and fonts: cache-first (safe, don't affect logic)
    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) {
                return cached;
            }
            return fetch(event.request).then((response) => {
                // Cache the fetched response for next time
                if (response.ok) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            });
        })
    );
});
