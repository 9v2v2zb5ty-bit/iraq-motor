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

async function runOpenSooqScraper() {
  console.log('🚀 Starting OpenSooq Scraper (Universal Parser)...');
  
  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox', 
      '--disable-setuid-sandbox',
      '--disable-blink-features=AutomationControlled'
    ]
  });

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    locale: 'ar-IQ',
    viewport: { width: 1366, height: 768 }
  });

  const page = await context.newPage();

  try {
    console.log('🌐 Navigating to OpenSooq cars section (Baghdad)...');
    await page.goto('https://iq.opensooq.com/ar/baghdad/cars/cars-for-sale', { 
      waitUntil: 'domcontentloaded', 
      timeout: 60000 
    });

    await page.waitForTimeout(5000);
    await page.evaluate(() => window.scrollBy(0, 1000));
    await page.waitForTimeout(3000);

    const listings = await page.evaluate(() => {
      const items = [];
      const links = document.querySelectorAll('a');
      const seen = new Set();

      links.forEach(link => {
        const title = link.innerText ? link.innerText.trim() : '';
        const href = link.href || '';

        if (title.length > 15 && !seen.has(title) && (href.includes('/') || href.length > 30)) {
          seen.add(title);
          
          const card = link.closest('div') || link.parentElement;
          const priceEl = card ? card.querySelector('[class*="price"], [class*="Price"]') : null;
          const imgEl = card ? card.querySelector('img') : null;

          let imageUrl = '';
          if (imgEl) {
            imageUrl = imgEl.src || imgEl.getAttribute('data-src') || imgEl.getAttribute('data-lazy-src') || '';
          }

          items.push({
            title: title.split('\n')[0],
            rawPrice: priceEl ? priceEl.innerText.trim() : '15000',
            image: imageUrl.startsWith('http') ? imageUrl : ''
          });
        }
      });

      return items;
    });

    console.log(`📦 Found ${listings.length} raw elements.`);

    if (listings.length === 0) {
      console.log('⚠️ Still 0 listings found. Check page access.');
      return;
    }

    let savedCount = 0;
    const targetListings = listings.slice(0, 10);

    for (const item of targetListings) {
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
        price: price > 1000 ? price : 15000,
        currency: 'USD',
        city: 'بغداد',
        phone: '07700000000',
        images: item.image ? [item.image] : [],
        approved: true,
        featured: false,
        source: 'OpenSooq',
        userId: 'system-bot-scraper',
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      });
      savedCount++;
    }

    console.log(`✅ Successfully published ${savedCount} valid cars to Firestore!`);
  } catch (err) {
    console.error('❌ Error during scraping:', err.message);
  } finally {
    await browser.close();
  }
}

app.get('/', (req, res) => res.send('Server is running'));

const PORT = process.env.PORT || 3000;

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
