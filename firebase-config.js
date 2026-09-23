// firebase-config.js
// -----------------------------------------------------------------------
// Native Firebase Phone Auth (SMS OTP) for registration.
//
// IMPORTANT: this file is intentionally written for the classic Firebase
// compat SDK, not ES modules. This is the most reliable method on iPad
// Safari and on some hosting setups where module scripts may fail to load
// or show up as "not loaded" even though the page appears to be open.
//
// We reuse the same Firebase app that index.html already initializes,
// instead of calling initializeApp() again.
// -----------------------------------------------------------------------

(function () {
  if (!window.firebase || !window.firebase.auth) {
    console.error('Firebase compat SDK not ready yet.');
    return;
  }

  const auth = window.firebase.auth();

  function initRecaptcha() {
    const container = document.getElementById('recaptcha-container');
    if (!container) {
      throw new Error('missing-recaptcha-container');
    }

    if (window.recaptchaVerifier) {
      try { window.recaptchaVerifier.clear(); } catch (e) {}
      window.recaptchaVerifier = null;
    }

    window.recaptchaVerifier = new firebase.auth.RecaptchaVerifier(container, { size: 'invisible' });
    return window.recaptchaVerifier;
  }

  function formatIraqiPhone(phone) {
    let cleaned = String(phone || '').replace(/\D/g, '');
    if (cleaned.startsWith('964')) cleaned = cleaned.slice(3);
    if (cleaned.startsWith('0')) cleaned = cleaned.slice(1);
    return `+964${cleaned}`;
  }

  window.sendOTP = async function(phoneNumber) {
    try {
      const appVerifier = initRecaptcha();
      const formattedPhone = formatIraqiPhone(phoneNumber);
      window.confirmationResult = await auth.signInWithPhoneNumber(formattedPhone, appVerifier);
      return { success: true };
    } catch (error) {
      console.error('sendOTP error:', error);

      let msg = 'تعذر إرسال الرمز، حاول لاحقاً';
      if (error && error.code === 'auth/too-many-requests') msg = 'محاولات كثيرة على هذا الرقم، حاول بعد شوي';
      if (error && error.code === 'auth/invalid-phone-number') msg = 'رقم الهاتف غير صحيح';
      if (error && error.code === 'auth/network-request-failed') msg = 'فشل الاتصال بالخادم، تأكد من الإنترنت ثم حاول مرة ثانية';
      if (error && error.code === 'auth/internal-error') msg = 'مشكلة في خدمة Firebase أو في إعدادات reCAPTCHA / النطاق المصرح به';
      if (error && error.code === 'auth/captcha-check-failed') msg = 'فشل التحقق البصري (reCAPTCHA)، أعد تحميل الصفحة ثم حاول مرة ثانية';
      if (error && error.message && error.message.includes('missing-recaptcha-container')) {
        msg = 'عنصر التحقق غير موجود في الصفحة، أعد تحميل الصفحة ثم حاول مرة ثانية';
      }

      return { success: false, message: msg, code: error && error.code ? error.code : null };
    }
  };

  window.verifyOTP = async function(code) {
    try {
      if (!window.confirmationResult) return { success: false, message: 'اطلب رمز تحقق أولاً' };
      const result = await window.confirmationResult.confirm(code);
      return { success: true, user: result.user };
    } catch (error) {
      console.error('verifyOTP error:', error);
      return { success: false, message: 'الرمز غير صحيح' };
    }
  };

  window.linkPasswordAndProfile = async function(name, password) {
    try {
      const user = auth.currentUser;
      if (!user) throw { code: 'no_user' };

      const fakeEmail = user.phoneNumber.replace('+', '') + '@phone.iraqmotors.site';
      const emailCred = firebase.auth.EmailAuthProvider.credential(fakeEmail, password);
      await user.linkWithCredential(emailCred);
      await user.updateProfile({ displayName: name });
      return { success: true, uid: user.uid, phone: user.phoneNumber };
    } catch (error) {
      console.error('linkPasswordAndProfile error:', error);
      let msg = 'صار خطأ، حاول مرة ثانية';
      if (error && (error.code === 'auth/email-already-in-use' || error.code === 'auth/credential-already-in-use')) {
        msg = 'هذا الرقم مسجل مسبقاً، جرب تسجيل الدخول';
      }
      return { success: false, message: msg };
    }
  };
})();
