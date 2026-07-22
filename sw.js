// Iraq Motors - Service Worker
const CACHE_NAME = 'iraq-motors-v1';
const APP_SHELL = [
  './iraq-motors_6.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png',
  './icons/favicon-16.png'
];

// عند تثبيت الـ Service Worker: تخزين ملفات التطبيق الأساسية
self.addEventListener('install', function(event) {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(APP_SHELL);
    })
  );
});

// عند التفعيل: حذف أي نسخ كاش قديمة
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(key) { return key !== CACHE_NAME; })
            .map(function(key) { return caches.delete(key); })
      );
    }).then(function() { return self.clients.claim(); })
  );
});

// استراتيجية الجلب: الشبكة أولاً، والرجوع للكاش عند انقطاع الاتصال
self.addEventListener('fetch', function(event) {
  const req = event.request;

  if (req.method !== 'GET') return;

  event.respondWith(
    fetch(req)
      .then(function(res) {
        // تحديث الكاش بنسخة جديدة عند نجاح الطلب (لطلبات نفس الموقع فقط)
        if (req.url.startsWith(self.location.origin)) {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(req, resClone);
          });
        }
        return res;
      })
      .catch(function() {
        return caches.match(req).then(function(cached) {
          if (cached) return cached;
          // إذا كان طلب تصفح صفحة ولا يوجد اتصال، أرجع الصفحة الرئيسية من الكاش
          if (req.mode === 'navigate') {
            return caches.match('./iraq-motors_6.html');
          }
        });
      })
  );
});
