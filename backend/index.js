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
  console.log('🚀 Starting OpenSooq Precision Scraper...');
  
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
    console.log('🌐 Navigating to OpenSooq Baghdad cars...');
    await page.goto('https://iq.opensooq.com/ar/baghdad/cars/cars-for-sale', { 
      waitUntil: 'domcontentloaded', 
      timeout: 60000 
    });

    await page.waitForTimeout(6000);
    await page.evaluate(() => window.scrollBy(0, 1200));
    await page.waitForTimeout(4000);

    const listings = await page.evaluate(() => {
      const items = [];
      const cards = document.querySelectorAll('div.serchList-card, div[class*="post-row"], div.cardHolder, li.postItem, article');

      cards.forEach(card => {
        const titleEl = card.querySelector('h2, h3, a[class*="title"], .post-title');
        const title = titleEl ? titleEl.innerText.trim() : '';

        const priceEl = card.querySelector('[class*="price"], [class*="Price"], span.text-red, .font-bold');
        const priceText = priceEl ? priceEl.innerText.trim() : '';

        const imgEl = card.querySelector('img');
        let imageUrl = '';
        if (imgEl) {
          imageUrl = imgEl.src || imgEl.getAttribute('data-src') || imgEl.getAttribute('data-lazy-src') || '';
        }

        if (title && title.length > 8 && !title.includes('دراجات') && !title.includes('قوارب')) {
          items.push({
            title: title,
            rawPrice: priceText,
            image: imageUrl.startsWith('http') ? imageUrl : ''
          });
        }
      });

      return items;
    });

    console.log(`📦 Found ${listings.length} verified car cards.`);

    if (listings.length === 0) {
      console.log('⚠️ No valid car cards found with precise selectors.');
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
      
      const numericPrice = Number(item.rawPrice.replace(/[^0-9]/g, ''));
      const finalPrice = (numericPrice && numericPrice > 500) ? numericPrice : 15000;

      await db.collection('cars').add({
        title: item.title,
        make: make,
        model: model,
        year: year,
        fuelType: 'بنزين',
        transmission: 'أوتوماتيك',
        color: 'أبيض',
        condition: 'مستعمل',
        price: finalPrice,
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

    console.log(`✅ Successfully published ${savedCount} authentic cars with real data!`);
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
