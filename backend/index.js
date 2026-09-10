const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');
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

// دالة الكشط الفعالة والمحدثة
async function runOpenSooqScraper() {
  console.log('🚀 Starting OpenSooq Scraper...');
  
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    locale: 'ar-IQ'
  });

  const page = await context.newPage();

  try {
    console.log('🌐 Navigating to OpenSooq cars section...');
    await page.goto('https://iq.opensooq.com/ar/عمان/سيارات-للسيارات/سيارات-للبيع', { 
      waitUntil: 'domcontentloaded', 
      timeout: 60000 
    });

    await page.waitForTimeout(4000);

    // سحب الإعلانات من الصفحة
    const listings = await page.evaluate(() => {
      const items = [];
      const links = document.querySelectorAll('a[href*="/ar/post/"]');
      const seen = new Set();

      links.forEach(link => {
        const title = link.innerText.trim();
        const href = link.href;

        if (title && title.length > 5 && !seen.has(title)) {
          seen.add(title);
          const card = link.closest('li') || link.closest('div') || link.parentElement;
          const priceText = card ? (card.querySelector('[class*="price"], [class*="Price"]')?.innerText || '') : '';
          const imgEl = card ? card.querySelector('img') : null;

          items.push({
            title: title,
            rawPrice: priceText,
            image: imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : ''
          });
        }
      });

      return items;
    });

    console.log(`📦 Found ${listings.length} raw listings.`);

    if (listings.length === 0) {
      console.log('⚠️ No listings found. Check selectors or blocking.');
      return;
    }

    let savedCount = 0;
    for (const item of listings) {
      const titleWords = item.title.split(' ');
      const make = titleWords[0] || 'تويوتا';
      const model = titleWords[1] || 'كورولا';
      
      const yearMatch = item.title.match(/\b(20[0-2][0-9]|19[9][0-9])\b/);
      const year = yearMatch ? Number(yearMatch[0]) : 2022;
      const price = Number(item.rawPrice.replace(/[^0-9]/g, '')) || 15000;

      await db.collection('cars').add({
        title: item.title,
        make: make,
        model: model,
        year: year,
        fuelType: 'بنزين',
        transmission: 'أوتوماتيك',
        color: 'أبيض',
        condition: 'مستعمل',
        price: price,
        currency: 'USD',
        city: 'بغداد',
        phone: '07700000000',
        images: item.image ? [item.image] : [],
        approved: true, // تفعيل فورياً ليظهر في الموقع
        featured: false,
        source: 'OpenSooq',
        userId: 'system-bot-scraper',
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      });
      savedCount++;
    }

    console.log(`✅ Successfully published ${savedCount} cars to Firestore!`);
  } catch (err) {
    console.error('❌ Error during scraping:', err.message);
  } finally {
    await browser.close();
  }
}

app.get('/', (req, res) => res.send('Server is running'));

const PORT = process.env.PORT || 3000;

// التحقق من حالة التشغيل (once) لتنفيذ السكربت عبر GitHub Actions
if (process.argv.includes('once')) {
  console.log('⚙️ Running in scraper mode (once)...');
  runOpenSooqScraper().then(() => {
    console.log('🏁 Task completed successfully.');
    process.exit(0);
  }).catch(err => {
    console.error('❌ Task failed:', err);
    process.exit(1);
  });
} else {
  app.listen(PORT, () => console.log('🚀 Server listening on port ' + PORT));
}
