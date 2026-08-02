// Iraq Motors - Service Worker
const CACHE_NAME = 'iraq-motors-v2';
const APP_SHELL = [
  './',
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

// عند التفعيل: حذف أي نسخ كاش قديمة (تشمل أي نسخة كانت قد خزّنت صفحة خطأ بالغلط)
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

// استراتيجية الجلب: الشبكة أولاً (بتجاوز كاش المتصفح)، والرجوع للكاش عند انقطاع الاتصال
self.addEventListener('fetch', function(event) {
  const req = event.request;

  if (req.method !== 'GET') return;

  const isSameOrigin = req.url.startsWith(self.location.origin);

  event.respondWith(
    fetch(req, { cache: 'no-store' })
      .then(function(res) {
        // روابط خارجية (خطوط Google مثلاً): مرّرها كما هي بدون فحص أو تخزين
        if (!isSameOrigin) return res;

        // خزّن فقط الاستجابات الناجحة (نتجاهل 404/500 حتى لا تُحفظ كنسخة صحيحة وتُعرض لاحقًا بدل الصفحة الحقيقية)
        if (res && res.ok) {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(req, resClone); });
          return res;
        }

        // استجابة غير ناجحة (مثلاً رابط مباشر لإعلان سيارة لا يعرفه الاستضافة) -> نسخة محفوظة، وإلا الصفحة الرئيسية المحفوظة
        return caches.match(req).then(function(cached) {
          return cached || (req.mode === 'navigate' ? caches.match('./') : res);
        });
      })
      .catch(function() {
        return caches.match(req).then(function(cached) {
          if (cached) return cached;
          // إذا كان طلب تصفح صفحة ولا يوجد اتصال، أرجع الصفحة الرئيسية من الكاش
          if (req.mode === 'navigate') {
            return caches.match('./');
          }
        });
      })
  );
});
