// يجيب السيارات من Firestore ويكتب عددها وقائمتها داخل index.html و 404.html
// (عشان ChatGPT / Gemini / جوجل يشوفونها بدون جافاسكربت)
import fs from 'node:fs';

const PROJECT = 'iraq-motors-38983';
const FILES = ['index.html', '404.html'].filter((f) => fs.existsSync(f));

const r = await fetch(`https://firestore.googleapis.com/v1/projects/${PROJECT}/databases/(default)/documents:runQuery`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    structuredQuery: {
      from: [{ collectionId: 'cars' }],
      where: { fieldFilter: { field: { fieldPath: 'approved' }, op: 'EQUAL', value: { booleanValue: true } } },
      select: { fields: ['make', 'model', 'year', 'price', 'currency', 'city', 'sold'].map((f) => ({ fieldPath: f })) },
      limit: 1000,
    },
  }),
});
if (!r.ok) { console.error('Firestore error', r.status, await r.text()); process.exit(1); }

const v = (f) => (f ? f.stringValue ?? f.integerValue ?? f.doubleValue ?? f.booleanValue : undefined);
const all = (await r.json()).filter((x) => x.document).map(({ document }) => {
  const f = document.fields || {};
  return { make: v(f.make), model: v(f.model), year: v(f.year), price: Number(v(f.price)) || 0, currency: v(f.currency) || 'USD', city: v(f.city), sold: v(f.sold) === true };
});
// حماية: إذا رجع صفر (خطأ مؤقت) لا نكتب فوق آخر نسخة سليمة
if (all.length === 0) { console.log('No cars returned, skipping update'); process.exit(0); }

const avail = all.filter((c) => !c.sold);
const esc = (s) => String(s ?? '').replace(/[<>&"]/g, '');
const name = (c) => esc([c.make, c.model, c.year].filter(Boolean).join(' '));
const priceTxt = (c) => (c.price ? (c.currency === 'IQD' ? c.price.toLocaleString('en-US') + ' IQD' : '$' + c.price.toLocaleString('en-US')) : '');
const top = avail.slice(0, 100);

const ld = JSON.stringify({
  '@context': 'https://schema.org', '@type': 'ItemList',
  name: 'السيارات المعروضة في Iraq Motors', numberOfItems: avail.length,
  itemListElement: top.map((c, i) => ({
    '@type': 'ListItem', position: i + 1,
    item: {
      '@type': 'Car', name: name(c),
      ...(c.price ? { offers: { '@type': 'Offer', price: c.price, priceCurrency: c.currency === 'IQD' ? 'IQD' : 'USD' } } : {}),
      ...(c.city ? { availableAtOrFrom: { '@type': 'Place', name: esc(c.city) } } : {}),
    },
  })),
}).replace(/</g, '\\u003c');

const head = `<script type="application/ld+json">${ld}</script>`;
const HIDE = 'position:absolute;width:1px;height:1px;margin:-1px;padding:0;border:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap';
const body = `<div id="seo-snapshot" style="${HIDE}"><h2>Iraq Motors - سيارات معروضة للبيع في العراق</h2><p>عدد السيارات المعروضة حالياً في الموقع: ${avail.length}. الموقع شغال ومفتوح للجميع.</p><ul>${top.map((c) => `<li>${name(c)}${priceTxt(c) ? ' - ' + priceTxt(c) : ''}${c.city ? ' - ' + esc(c.city) : ''}</li>`).join('')}</ul></div>`;

// ملاحظة: نستعمل دالة بدل نص للاستبدال، لأن علامة $ بالأسعار ($20,000) كانت تخرّب الاستبدال.
// والمطابقة greedy (من أول علامة بداية لآخر علامة نهاية) حتى تصلّح أي ملف انخرب سابقاً.
const swap = (html, tag, content) =>
  html.replace(
    new RegExp(`<!--SNAPSHOT_${tag}_START-->[\\s\\S]*<!--SNAPSHOT_${tag}_END-->`),
    () => `<!--SNAPSHOT_${tag}_START-->${content}<!--SNAPSHOT_${tag}_END-->`
  );

for (const file of FILES) {
  let html = fs.readFileSync(file, 'utf8');
  const before = html;
  html = swap(html, 'HEAD', head);
  html = swap(html, 'BODY', body);
  html = html.replace(/<span id="cntCars">[^<]*<\/span>/, () => `<span id="cntCars">${avail.length}</span>`);
  if (html !== before) { fs.writeFileSync(file, html); console.log('updated', file, '-', avail.length, 'cars'); }
  else console.log('no change', file);
}
