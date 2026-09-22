// firebase-config.js
// -----------------------------------------------------------------------
// Native Firebase Phone Auth (SMS OTP) for registration.
//
// IMPORTANT: this file does NOT call initializeApp() itself. index.html
// already initializes the Firebase app with firebase.initializeApp(...)
// using the classic "compat" scripts. This file just reuses that SAME
// app via getApp(), so there is only ever one app / one signed-in user
// state shared between this file and the rest of index.html. Calling
// initializeApp() a second time here would throw
// "Firebase App named '[DEFAULT]' already exists" (or worse, silently
// create a second, disconnected auth session).
//
// Load order is safe because <script type="module"> always runs AFTER
// the page has finished parsing, i.e. after the classic compat scripts
// (including the initializeApp(...) call) have already run — regardless
// of where in the HTML this script tag sits.
// -----------------------------------------------------------------------

import { getApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import {
  getAuth,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  EmailAuthProvider,
  linkWithCredential,
  updateProfile
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";

const app = getApp();          // reuses the app index.html already initialized
export const auth = getAuth(app);

// ---- invisible reCAPTCHA (recreated fresh on every send/resend) ----
function initRecaptcha(){
  if (window.recaptchaVerifier){
    try { window.recaptchaVerifier.clear(); } catch(e){}
    window.recaptchaVerifier = null;
  }
  window.recaptchaVerifier = new RecaptchaVerifier(auth, 'recaptcha-container', { size: 'invisible' });
  return window.recaptchaVerifier;
}

// "07xxxxxxxxx" أو "7xxxxxxxxx" أو "+9647xxxxxxxxx" → "+9647xxxxxxxxx"
function formatIraqiPhone(phone){
  let cleaned = phone.replace(/\D/g, '');
  if (cleaned.startsWith('964')) cleaned = cleaned.slice(3);
  if (cleaned.startsWith('0')) cleaned = cleaned.slice(1);
  return `+964${cleaned}`;
}

// يرجع {success, message} بدل alert() حتى تعرض index.html الرسالة بنفس ستايل الموقع
window.sendOTP = async function(phoneNumber){
  try{
    const appVerifier = initRecaptcha();
    const formattedPhone = formatIraqiPhone(phoneNumber);
    window.confirmationResult = await signInWithPhoneNumber(auth, formattedPhone, appVerifier);
    return { success: true };
  }catch(error){
    console.error("sendOTP error:", error);
    let msg = 'تعذر إرسال الرمز، حاول لاحقاً';
    if (error.code === 'auth/too-many-requests') msg = 'محاولات كثيرة على هذا الرقم، حاول بعد شوي';
    if (error.code === 'auth/invalid-phone-number') msg = 'رقم الهاتف غير صحيح';
    return { success: false, message: msg };
  }
};

window.verifyOTP = async function(code){
  try{
    if (!window.confirmationResult) return { success:false, message:'اطلب رمز تحقق أولاً' };
    const result = await window.confirmationResult.confirm(code);
    return { success: true, user: result.user };
  }catch(error){
    console.error("verifyOTP error:", error);
    return { success: false, message: 'الرمز غير صحيح' };
  }
};

// يربط باسورد + اسم بنفس الحساب اللي تحقق برقمه، حتى تسجيل الدخول القادم
// يصير بالرقم + الباسورد (بدون حاجة لرمز تحقق جديد بكل مرة)
window.linkPasswordAndProfile = async function(name, password){
  try{
    const user = auth.currentUser;
    if (!user) throw { code: 'no_user' };
    const fakeEmail = user.phoneNumber.replace('+', '') + '@phone.iraqmotors.site';
    await linkWithCredential(user, EmailAuthProvider.credential(fakeEmail, password));
    await updateProfile(user, { displayName: name });
    return { success: true, uid: user.uid, phone: user.phoneNumber };
  }catch(error){
    console.error("linkPasswordAndProfile error:", error);
    let msg = 'صار خطأ، حاول مرة ثانية';
    if (error.code === 'auth/email-already-in-use' || error.code === 'auth/credential-already-in-use') {
      msg = 'هذا الرقم مسجل مسبقاً، جرب تسجيل الدخول';
    }
    return { success: false, message: msg };
  }
};
