// --- دالة الكشط المحسّنة ---
async function runOpenSooqScraper() {
  console.log('Starting OpenSooq Scraper...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  try {
    // 1. الانتقال إلى قسم السيارات في العراق
    await page.goto('https://iq.opensooq.com/ar/عمان/سيارات-للسيارات/سيارات-للبيع', { 
      waitUntil: 'networkidle', 
      timeout: 60000 
    });

    // 2. الانتظار حتى تحميل الإعلانات
    await page.waitForTimeout(5000);

    // 3. استخراج الإعلانات
    const listings = await page.evaluate(() => {
      const items = [];
      // البحث عن كروت الإعلانات بكل المسميات المحتملة في السوق المفتوح
      const cards = document.querySelectorAll('li[data-id], div[class*="PostCard"], article, .post-card');
      
      cards.forEach(card => {
        const titleEl = card.querySelector('h2, h3, [class*="title"], [class*="Title"]');
        const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
        const imgEl = card.querySelector('img');
        const linkEl = card.querySelector('a');

        if (titleEl && titleEl.innerText.trim()) {
          items.push({
            title: titleEl.innerText.trim(),
            price: priceEl ? priceEl.innerText.trim() : 'السعر عند الاتصال',
            image: imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : '',
            link: linkEl ? linkEl.href : '',
            approved: true,
            source: 'OpenSooq'
          });
        }
      });
      return items;
    });

    console.log(`Scraped ${listings.length} listings.`);

    // 4. حفظ البيانات في Firestore
    for (const item of listings) {
      await db.collection('cars').add({
        ...item,
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      });
    }

    console.log('All scraped listings published to Firestore successfully.');
  } catch (err) {
    console.error('Error during scraping:', err.message);
  } finally {
    await browser.close();
  }
}
