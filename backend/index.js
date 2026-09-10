async function runOpenSooqScraper() {
  console.log('Starting OpenSooq Scraper with Full Schema...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  try {
    // 1. فتح قسم السيارات في العراق
    await page.goto('https://iq.opensooq.com/ar/عمان/سيارات-للسيارات/سيارات-للبيع', { 
      waitUntil: 'networkidle', 
      timeout: 60000 
    });

    await page.waitForTimeout(4000);

    // 2. كشط البيانات وتحليل الحقول المطلوبة للموقع
    const rawListings = await page.evaluate(() => {
      const items = [];
      const cards = document.querySelectorAll('li[data-id], div[class*="PostCard"], article, .post-card');
      
      cards.forEach(card => {
        const titleEl = card.querySelector('h2, h3, [class*="title"], [class*="Title"]');
        const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
        const imgEl = card.querySelector('img');
        const cityEl = card.querySelector('[class*="city"], [class*="location"]');

        if (titleEl && titleEl.innerText.trim()) {
          items.push({
            fullTitle: titleEl.innerText.trim(),
            rawPrice: priceEl ? priceEl.innerText.trim() : '0',
            image: imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : '',
            city: cityEl ? cityEl.innerText.trim() : 'بغداد'
          });
        }
      });
      return items;
    });

    console.log(`Scraped ${rawListings.length} raw listings.`);

    // 3. تحويل وتجهيز البيانات للتوافق مع شروط موقعك (Schema Matching)
    for (const item of rawListings) {
      const titleWords = item.fullTitle.split(' ');
      const make = titleWords[0] || 'سيارة';
      const model = titleWords[1] || 'عام';
      
      // استخراج سنة الصنع من العنوان إن وجدت، وإلا اعتماد سنة حديثة
      const yearMatch = item.fullTitle.match(/\b(20[0-2][0-9]|19[9][0-9])\b/);
      const year = yearMatch ? Number(yearMatch[0]) : 2022;

      // تحويل السعر إلى رقم
      const numericPrice = Number(item.rawPrice.replace(/[^0-9]/g, '')) || 12000;

      // إضافة المستند إلى Firestore بنفس الهيكل المرفق بصورتك
      await db.collection('cars').add({
        title: item.fullTitle,
        make: make,
        model: model,
        year: year,
        fuelType: 'بنزين',
        transmission: 'أوتوماتيك',
        color: 'أبيض',
        condition: 'مستعمل',
        price: numericPrice,
        currency: 'USD',
        city: item.city || 'بغداد',
        phone: '07700000000',
        images: item.image ? [item.image] : [],
        approved: true, // تفعيل الإعلان مباشرة ليظهر في الصفحة الرئيسية
        featured: false,
        source: 'OpenSooq',
        userId: 'system-bot-scraper', // معرف المستخدم الآلي
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      });
    }

    console.log('All listings formatted and published successfully!');
  } catch (err) {
    console.error('Error during scraping:', err.message);
  } finally {
    await browser.close();
  }
}
