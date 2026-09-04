// generate-previews.js
//
// يحل مشكلة معاينة روابط السيارات على واتساب وجوجل: الموقع Single Page App
// (كل شي بجافاسكربت)، فبرامج زي واتساب وفيسبوك ما تشغّل جافاسكربت — تكتفي بقراءة
// وسوم <meta> الجاهزة بالصفحة وقت وصولها، فتشوف نفس العنوان/الصورة العامين
// لكل السيارات. هذا السكربت يبني صفحة HTML صغيرة لكل سيارة معتمدة، فيها
// وسوم Open Graph الصحيحة (العنوان، السعر، الصورة، الوصف) جاهزة بدون جافاسكربت،
// وتحوّل الزائر الحقيقي تلقائياً لتطبيق الموقع الكامل. يشتغل بدون أي كلمة سر:
// بيانات السيارات المعتمدة قابلة للقراءة العامة أصلاً حسب قواعد Firestore.
//
// يشغّله GitHub Actions (شوف .github/workflows/generate-previews.yml) على جدول
// دوري + يدوياً عند الحاجة — ما يحتاج أي إعداد إضافي غير رفع هذا الملف.

const https = require('https');
const fs = require('fs');
const path = require('path');

const PROJECT_ID = 'iraq-motors-38983';
const SITE_ORIGIN = 'https://iraqmotors.site';
const OUT_DIR = path.join(__dirname, '..', 'car');
const DEFAULT_IMAGE = SITE_ORIGIN + '/icons/apple-touch-icon.png';

function httpsGetJson(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}: ${data.slice(0, 300)}`));
          return;
        }
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

// Firestore REST API wraps every value in a {typeName: value} envelope.
// This unwraps a single document's `fields` object into plain JS values.
function unwrapFields(fields) {
  const out = {};
  if (!fields) return out;
  for (const key of Object.keys(fields)) {
    out[key] = unwrapValue(fields[key]);
  }
  return out;
}
function unwrapValue(v) {
  if (v == null) return null;
  if ('stringValue' in v) return v.stringValue;
  if ('integerValue' in v) return parseInt(v.integerValue, 10);
  if ('doubleValue' in v) return v.doubleValue;
  if ('booleanValue' in v) return v.booleanValue;
  if ('nullValue' in v) return null;
  if ('timestampValue' in v) return v.timestampValue;
  if ('arrayValue' in v) return (v.arrayValue.values || []).map(unwrapValue);
  if ('mapValue' in v) return unwrapFields(v.mapValue.fields);
  return null;
}

async function fetchApprovedCars() {
  const cars = [];
  let pageToken = null;
  do {
    const base = `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/(default)/documents/cars?pageSize=300`;
    const url = pageToken ? `${base}&pageToken=${encodeURIComponent(pageToken)}` : base;
    const page = await httpsGetJson(url);
    const docs = page.documents || [];
    for (const doc of docs) {
      const id = doc.name.split('/').pop();
      const data = unwrapFields(doc.fields);
      if (data.approved === true) cars.push(Object.assign({ id }, data));
    }
    pageToken = page.nextPageToken || null;
  } while (pageToken);
  return cars;
}

// Mirrors iqCarSlug() in index.html exactly, so generated URLs match the ones
// the live app itself already links to and pushState()s into the address bar.
function carSlug(car) {
  return [car.make, car.model, car.year]
    .filter(Boolean)
    .join('-')
    .toLowerCase()
    .replace(/[^a-z0-9\u0600-\u06FF]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

// Mirrors priceStr() in index.html.
function priceStr(car) {
  const price = car.price || 0;
  const formatted = price.toLocaleString('en-US');
  return car.currency === 'IQD' ? `${formatted} د.ع` : `$${formatted}`;
}

// Mirrors the carLabel / carDesc construction inside openCarDetail() in index.html.
function carLabel(car) {
  return [car.make, car.model, car.year].filter(Boolean).join(' ');
}
function carDesc(car) {
  const label = carLabel(car);
  const ps = priceStr(car);
  return `سيارة ${label} للبيع${car.city ? ' في ' + car.city : ''} بسعر ${ps} على Iraq Motors.`;
}
function carImage(car) {
  if (Array.isArray(car.imgs) && car.imgs.length) return car.imgs[0];
  if (car.img) return car.img;
  return DEFAULT_IMAGE;
}

function escapeHtml(s) {
  return String(s || '').replace(/[<>&"]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
}

function buildPreviewHtml(car) {
  const slug = carSlug(car);
  const carPath = `/car/${car.id}${slug ? '-' + slug : ''}`;
  const url = SITE_ORIGIN + carPath;
  const title = escapeHtml(`${carLabel(car)} | Iraq Motors`);
  const desc = escapeHtml(carDesc(car));
  const image = escapeHtml(carImage(car));
  const spaUrl = `${SITE_ORIGIN}/car/${car.id}`;

  return `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
<meta name="description" content="${desc}">
<link rel="canonical" href="${url}">
<meta name="robots" content="index, follow">

<meta property="og:type" content="website">
<meta property="og:site_name" content="Iraq Motors">
<meta property="og:locale" content="ar_IQ">
<meta property="og:title" content="${title}">
<meta property="og:description" content="${desc}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${image}">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${title}">
<meta name="twitter:description" content="${desc}">
<meta name="twitter:image" content="${image}">

<!-- Crawlers (WhatsApp/Facebook/Google/...) stop right here and read the tags
     above. Real visitors get redirected instantly into the full app below. -->
<meta http-equiv="refresh" content="0; url=${spaUrl}">
<script>location.replace(${JSON.stringify(spaUrl)});</script>
</head>
<body>
<p>جاري التحويل إلى صفحة السيارة… <a href="${spaUrl}">اضغط هنا إذا لم يتم التحويل تلقائياً</a></p>
</body>
</html>
`;
}

function buildSitemap(cars) {
  const staticPaths = ['/', '/cars', '/dealers', '/agencies'];
  const urls = staticPaths.map((p) => `  <url><loc>${SITE_ORIGIN}${p}</loc></url>`);
  for (const car of cars) {
    const slug = carSlug(car);
    const carPath = `/car/${car.id}${slug ? '-' + slug : ''}`;
    urls.push(`  <url><loc>${SITE_ORIGIN}${carPath}</loc></url>`);
  }
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`;
}

async function main() {
  console.log('Fetching approved cars from Firestore...');
  const cars = await fetchApprovedCars();
  console.log(`Found ${cars.length} approved cars.`);

  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });

  for (const car of cars) {
    const slug = carSlug(car);
    const fileName = `${car.id}${slug ? '-' + slug : ''}.html`;
    fs.writeFileSync(path.join(OUT_DIR, fileName), buildPreviewHtml(car), 'utf8');
    // Also write a copy at the bare ID (no slug) so /car/<id> (no slug in the
    // URL) resolves too, matching how the SPA itself builds links.
    if (slug) {
      fs.writeFileSync(path.join(OUT_DIR, `${car.id}.html`), buildPreviewHtml(car), 'utf8');
    }
  }

  const sitemapPath = path.join(__dirname, '..', 'sitemap.xml');
  fs.writeFileSync(sitemapPath, buildSitemap(cars), 'utf8');

  console.log(`Wrote ${cars.length} preview pages to ${OUT_DIR}`);
  console.log(`Wrote sitemap to ${sitemapPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
