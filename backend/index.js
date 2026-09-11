const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');
const crypto = require('crypto');
const fs = require('fs');
const { chromium } = require('playwright');

if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert(JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT))
  });
}

const db = admin.firestore();
const app = express();
app.use(cors());
app.use(express.json());

/*
  شنو تغير عن النسخة القديمة:

  1. ما نخمن أسماء classes (h2, h3, article, div.cardHolder...) - هذا كان
     السبب الحقيقي وراء "اسم السيارة غلط": كانت تطابق عناوين مواصفات/فلاتر
     بالصفحة (زي "الهيكل"، "نوع الوقود") مو عناوين إعلانات فعلية.
     بدالها نلقى روابط الإعلانات الحقيقية أول (عن طريق شكل الرابط) ونطلع
     منها للبطاقة اللي تحتويها. LISTING_LINK_PATTERN تحت متأكد منه فعليًا
     من لوق تشغيلة debug حقيقية (نمط /ar/search/<رقم>) - مو تخمين.

  2. حذفنا رقم الهاتف المزيف بالكامل. ما نسحب رقم هاتف حقيقي مال صاحب
     الإعلان الأصلي بدون علمه، وما نخترع رقم وهمي وننشره كأنه حقيقي.
     بدالها فيه رابط يرجع للإعلان الأصلي (sourceUrl).

  3. إذا العنوان أو السعر ما انسحب صح، الإعلان ينتجاوز (skip) بدل ما ينشر
     بأرقام مختلقة (كان فيه fallback على 15000، وmake/model افتراضي).

  4. dedup حقيقي: نستخدم رابط الإعلان كمعرف ثابت (document ID) بدل ما نضيف
     مستند جديد بكل تشغيلة - فنفس الإعلان ينحدّث مو ينتكرر.
*/

const LISTING_LINK_PATTERN = /\/ar\/search\/\d+/; // ✅ متأكد منه من اللوق - نمط رابط إعلان حقيقي

async function runOpenSooqScraper({ debugMode = false } = {}) {
  console.log('🚀 Starting OpenSooq scraper...');

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
  });

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    locale: 'ar-IQ',
    viewport: { width: 1366, height: 768 }
  });

  const page = await context.newPage();

  try {
    console.log('🌐 Navigating to OpenSooq Baghdad cars...');
    await page.goto('https://iq.opensooq.com/ar/baghdad/cars/cars-for-sale', {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(8000);
    await page.evaluate(() => window.scrollBy(0, 1200));
    await page.waitForTimeout(7000);

    if (debugMode) {
      // نطبع كل شي مفيد بضربة وحدة: العنوان، الرابط الحالي، معاينة النص،
      // وعدد الروابط - عشان نعرف هل الصفحة الحقيقية طلعت أصلاً أو صفحة حجب/تحقق
      const pageInfo = await page.evaluate(() => ({
        url: location.href,
        title: document.title,
        bodyPreview: (document.body ? document.body.innerText : '').replace(/\s+/g, ' ').slice(0, 300),
        hrefs: Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href'))
      }));

      console.log('🔗 Current URL:', pageInfo.url);
      console.log('📄 Page title:', pageInfo.title);
      console.log('📝 Body preview:', pageInfo.bodyPreview);

      const unique = [...new Set(pageInfo.hrefs.filter(Boolean))];
      // روابط الأقسام (دراجات، قوارب...) ما فيها أرقام أبدًا - روابط الإعلانات
      // الحقيقية غالبًا فيها رقم (سنة، سعر، أو ID) فنفلتر عليه لنلقاها
      const withDigit = unique.filter(h => /\d/.test(h));
      const withoutDigit = unique.filter(h => !/\d/.test(h));

      console.log(`🔗 ${unique.length} unique links total — ${withDigit.length} فيها رقم، ${withoutDigit.length} بدون رقم (غالبًا أقسام).`);
      console.log('🎯 عينة من الروابط اللي فيها رقم (مرشحة تكون إعلانات حقيقية):');
      withDigit.slice(0, 20).forEach(h => console.log('  ' + h));

      fs.writeFileSync('debug-page.html', await page.content());
      await page.screenshot({ path: 'debug-screenshot.png', fullPage: true });
      console.log('📝 Also saved debug-page.html + debug-screenshot.png (مفيدة بس لو تشغلها لوكال).');
      return;
    }

    const listings = await page.evaluate((linkPatternSrc) => {
      const linkPattern = new RegExp(linkPatternSrc, 'i');
      const seen = new Set();
      const items = [];

      Array.from(document.querySelectorAll('a[href]'))
        .filter(a => linkPattern.test(a.getAttribute('href') || ''))
        .forEach(link => {
          // اطلع لين نلگى بطاقة تحتوي رقم (سعر غالبًا)، أو نوقف عند 6 مستويات
          let card = link;
          for (let i = 0; i < 6 && card.parentElement; i++) {
            card = card.parentElement;
            if (/\d{3,}/.test(card.innerText || '')) break;
          }

          if (seen.has(card)) return;
          seen.add(card);

          const titleEl = card.querySelector('h2, h3, [class*="title" i]') || link;
          const title = (titleEl.innerText || '').trim();

          const priceEl = card.querySelector('[class*="price" i]');
          const rawPrice = priceEl ? priceEl.innerText.trim() : '';

          const imgEl = card.querySelector('img');
          const image = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '') : '';

          const href = link.getAttribute('href') || '';
          const sourceUrl = href.startsWith('http') ? href : `https://iq.opensooq.com${href}`;

          items.push({ title, rawPrice, image, sourceUrl });
        });

      return items;
    }, LISTING_LINK_PATTERN.source);

    console.log(`📦 Found ${listings.length} candidate listings.`);

    let saved = 0;
    let skipped = 0;

    for (const item of listings.slice(0, 10)) {
      const price = Number((item.rawPrice || '').replace(/[^0-9]/g, ''));
      const validTitle = item.title && item.title.length > 8;
      const validPrice = price > 500;
      const validImage = item.image && item.image.startsWith('http');

      // ما ننشر بيانات ناقصة أو مختلقة - نتجاوزها بدل ما نخمن قيمة
      if (!validTitle || !validPrice || !item.sourceUrl) {
        skipped++;
        continue;
      }

      const docId = crypto.createHash('md5').update(item.sourceUrl).digest('hex');

      await db.collection('cars').doc(docId).set({
        title: item.title,
        price,
        currency: 'USD',
        images: validImage ? [item.image] : [],
        sourceUrl: item.sourceUrl,
        source: 'OpenSooq',
        approved: true,
        featured: false,
        userId: 'system-bot-scraper',
        scrapedAt: admin.firestore.FieldValue.serverTimestamp()
      }, { merge: true });

      saved++;
    }

    console.log(`✅ ${saved} saved/updated, ${skipped} skipped for incomplete data.`);
  } catch (err) {
    console.error('❌ Error during scraping:', err.message);
  } finally {
    await browser.close();
  }
}

app.get('/', (req, res) => res.send('Server is running'));

const PORT = process.env.PORT || 3000;

if (process.argv.includes('debug')) {
  runOpenSooqScraper({ debugMode: true }).then(() => process.exit(0));
} else if (process.argv.includes('once')) {
  runOpenSooqScraper()
    .then(() => process.exit(0))
    .catch(err => {
      console.error('❌ Task failed:', err);
      process.exit(1);
    });
} else {
  app.listen(PORT, () => console.log('🚀 Server listening on port ' + PORT));
}
