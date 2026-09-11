/**
 * One-off cleanup: removes non-car listings (plates, parts, accessories,
 * hydraulic systems, electronics...) that were already published to the
 * `cars` collection before the category filter existed in index.js.
 *
 * Run once locally:
 *   1. Put your service-account.json in this same folder (or set the
 *      FIREBASE_SERVICE_ACCOUNT env var to its JSON content instead).
 *   2. npm install firebase-admin   (if not already installed)
 *   3. node cleanup-junk-listings.js
 *
 * It only deletes docs where source === 'OpenSooq' AND the title matches
 * a known non-car keyword, so manually-submitted or already-good listings
 * are never touched. It prints every title it deletes before committing.
 */

const fs = require('fs');
const admin = require('firebase-admin');

let credential;
if (process.env.FIREBASE_SERVICE_ACCOUNT) {
  credential = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
} else if (fs.existsSync('./service-account.json')) {
  credential = JSON.parse(fs.readFileSync('./service-account.json', 'utf8'));
} else {
  console.error(
    'No Firebase credentials found. Either set the FIREBASE_SERVICE_ACCOUNT ' +
      'env var to the JSON content, or place service-account.json next to this script.'
  );
  process.exit(1);
}

if (!admin.apps.length) {
  admin.initializeApp({ credential: admin.credential.cert(credential) });
}
const db = admin.firestore();

// Same denylist as index.js — keep the two in sync if you add more keywords there.
const NON_CAR_KEYWORDS = [
  'لوحات', 'أرقام مركبات', 'ارقام مركبات', 'أرقام', 'قطع', 'إكسسوار', 'اكسسوار',
  'كماليات', 'هيدروليك', 'الكتروني', 'إلكتروني', 'اطارات', 'إطارات',
  'زيوت', 'زيت', 'بطاريات', 'بطارية',
];

async function cleanup() {
  const snap = await db.collection('cars').where('source', '==', 'OpenSooq').get();
  console.log(`checking ${snap.size} OpenSooq-sourced listing(s)...`);

  const toDelete = [];
  snap.forEach((doc) => {
    const title = doc.data().title || '';
    if (NON_CAR_KEYWORDS.some((kw) => title.includes(kw))) {
      toDelete.push({ id: doc.id, title, ref: doc.ref });
    }
  });

  if (toDelete.length === 0) {
    console.log('nothing to delete — no matching non-car listings found.');
    return;
  }

  console.log(`found ${toDelete.length} non-car listing(s) to delete:`);
  toDelete.forEach((d) => console.log(`  - "${d.title}" (${d.id})`));

  const batch = db.batch();
  toDelete.forEach((d) => batch.delete(d.ref));
  await batch.commit();

  console.log(`done — deleted ${toDelete.length} listing(s).`);
}

cleanup()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error('cleanup failed:', err);
    process.exit(1);
  });
