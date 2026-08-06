const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');
const { randomUUID } = require('crypto');

admin.initializeApp({
  credential: admin.credential.cert(JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT))
});
const db = admin.firestore();
const app = express();
app.use(cors());
app.use(express.json());

const QI_API_HOST = process.env.QI_API_HOST;
const QI_USERNAME = process.env.QI_USERNAME;
const QI_PASSWORD = process.env.QI_PASSWORD;
const QI_TERMINAL_ID = process.env.QI_TERMINAL_ID;
const QI_WEBHOOK_URL = process.env.QI_WEBHOOK_URL;

const FEAT_PRICE_KEY = {3: 'featPrice3', 7: 'featPrice7', 15: 'featPrice15'};
const FEAT_PRICE_DEFAULT = {3: 5000, 7: 10000, 15: 20000};

function qiAuthHeader() {
  return 'Basic ' + Buffer.from(QI_USERNAME + ':' + QI_PASSWORD).toString('base64');
}
function qiHost() {
  return QI_API_HOST.replace(/\/$/, '');
}

async function verifyAuth(req) {
  const header = req.headers.authorization || '';
  const token = header.replace('Bearer ', '');
  if (!token) throw new Error('no-token');
  return admin.auth().verifyIdToken(token);
}

app.get('/', (req, res) => res.send('Iraq Motors backend OK'));

app.post('/createFeaturePayment', async (req, res) => {
  try {
    const decoded = await verifyAuth(req);
    const uid = decoded.uid;
    const carId = req.body.carId;
    const days = Number(req.body.days);
    const origin = (req.body.origin || '').replace(/\/$/, '');
    if (!carId || ![3, 7, 15].includes(days)) return res.status(400).json({error: 'بيانات غير صحيحة'});
    if (!origin) return res.status(400).json({error: 'origin مفقود'});

    const carSnap = await db.collection('cars').doc(carId).get();
    if (!carSnap.exists) return res.status(404).json({error: 'الإعلان غير موجود'});
    const car = carSnap.data();
    if (car.userId !== uid) return res.status(403).json({error: 'هذا الإعلان مو الك'});
    if (!car.approved) return res.status(400).json({error: 'الإعلان لازم يكون مفعّل أولاً'});

    const settingsSnap = await db.collection('settings').doc('general').get();
    const settings = settingsSnap.exists ? settingsSnap.data() : {};
    if (!settings.qiGatewayEnabled) return res.status(400).json({error: 'الدفع المباشر غير مفعّل حاليًا'});

    const price = Number(settings[FEAT_PRICE_KEY[days]]) || FEAT_PRICE_DEFAULT[days];
    const requestId = randomUUID();
    const carName = ((car.make || '') + ' ' + (car.model || '') + ' ' + (car.year || '')).trim();

    const reqRef = db.collection('featureRequests').doc(requestId);
    await reqRef.set({
      carId, carName, uid,
      userName: decoded.name || '',
      days, priceIQD: price, method: 'qicard_gateway',
      status: 'awaiting_payment',
      createdAt: admin.firestore.FieldValue.serverTimestamp()
    });

    const resp = await fetch(qiHost() + '/payment', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Terminal-Id': QI_TERMINAL_ID,
        'Authorization': qiAuthHeader()
      },
      body: JSON.stringify({
        requestId,
        amount: Number(price.toFixed(2)),
        currency: 'IQD',
        locale: 'ar',
        finishPaymentUrl: origin + '/#/profile?featurePaid=1&fr=' + requestId,
        notificationUrl: QI_WEBHOOK_URL,
        customerInfo: { firstName: decoded.name || 'User', phone: car.phone || '', accountId: uid },
        additionalInfo: {carId, days: String(days)}
      })
    });
    const data = await resp.json();
    if (!resp.ok || !data.formUrl) {
      await reqRef.update({status: 'failed', error: JSON.stringify(data).slice(0, 500)});
      return res.status(500).json({error: 'تعذر إنشاء عملية الدفع'});
    }
    await reqRef.update({paymentId: data.paymentId});
    res.json({formUrl: data.formUrl, requestId});
  } catch (e) {
    res.status(401).json({error: String(e)});
  }
});

async function confirmAndApply(requestId) {
  const reqRef = db.collection('featureRequests').doc(requestId);
  const reqSnap = await reqRef.get();
  if (!reqSnap.exists) return {ok: false, reason: 'not-found'};
  const reqData = reqSnap.data();
  if (reqData.status === 'approved' || reqData.status === 'rejected') {
    return {ok: true, status: reqData.status, already: true};
  }
  if (!reqData.paymentId) return {ok: false, reason: 'no-payment-id'};

  const resp = await fetch(qiHost() + '/payment/' + reqData.paymentId + '/status', {
    headers: {'X-Terminal-Id': QI_TERMINAL_ID, 'Authorization': qiAuthHeader()}
  });
  const confirmed = await resp.json();

  if (confirmed.status === 'SUCCESS') {
    const until = admin.firestore.Timestamp.fromDate(new Date(Date.now() + reqData.days * 86400000));
    await db.collection('cars').doc(reqData.carId).update({featured: true, featuredUntil: until});
    await reqRef.update({status: 'approved', gatewayStatus: confirmed.status, reviewedAt: admin.firestore.FieldValue.serverTimestamp()});
    await db.collection('notifications').add({
      title: 'تم تفعيل تمييز إعلانك ⭐',
      body: 'إعلانك "' + (reqData.carName || '') + '" الآن مميز لمدة ' + reqData.days + ' يوم.',
      audience: 'user', toUid: reqData.uid, toName: reqData.userName || null,
      sentBy: 'qi-gateway', createdAt: admin.firestore.FieldValue.serverTimestamp()
    });
    return {ok: true, status: 'approved'};
  }
  if (confirmed.status === 'FAILED' || confirmed.status === 'AUTHENTICATION_FAILED') {
    await reqRef.update({status: 'rejected', gatewayStatus: confirmed.status, reviewedAt: admin.firestore.FieldValue.serverTimestamp()});
    return {ok: true, status: 'rejected'};
  }
  return {ok: true, status: 'pending'};
}

app.post('/qiWebhook', async (req, res) => {
  try {
    const requestId = req.body && req.body.requestId;
    if (!requestId) return res.status(200).send('ignored');
    const result = await confirmAndApply(requestId);
    res.status(200).json(result);
  } catch (e) {
    res.status(200).send('error-logged');
  }
});

app.post('/checkFeaturePaymentStatus', async (req, res) => {
  try {
    const decoded = await verifyAuth(req);
    const requestId = req.body.requestId;
    if (!requestId) return res.status(400).json({error: 'requestId مفقود'});
    const reqSnap = await db.collection('featureRequests').doc(requestId).get();
    if (!reqSnap.exists || reqSnap.data().uid !== decoded.uid) return res.status(403).json({error: 'غير مسموح'});
    const result = await confirmAndApply(requestId);
    res.json(result);
  } catch (e) {
    res.status(401).json({error: String(e)});
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log('Server running on port ' + PORT));
