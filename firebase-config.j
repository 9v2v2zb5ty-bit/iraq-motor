import { initializeApp } from "firebase/app";
import { getAuth, RecaptchaVerifier, signInWithPhoneNumber } from "firebase/auth";

// ضع مفاتيح مشروعك هنا من Firebase Console
const firebaseConfig = {
  apiKey: "AIzaSyAb4MheuHSlF4yOxuDfhnxZtIMyXy7g-l8",
  authDomain: "iraq-motors.firebaseapp.com",
  projectId: "iraq-motors",
  storageBucket: "iraq-motors.appspot.com",
  messagingSenderId: "80307836321",
  appId: "1:80307836321:web:d61f734a86f5be5a4c67e0"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

// تهيئة Recaptcha الخفي
window.initRecaptcha = () => {
  if (!window.recaptchaVerifier && document.getElementById('recaptcha-container')) {
    window.recaptchaVerifier = new RecaptchaVerifier(auth, 'recaptcha-container', {
      'size': 'invisible'
    });
  }
};

// تحويل الرقم للترقيم الدولي +964
function formatIraqiPhone(phone) {
  let cleaned = phone.replace(/\D/g, '');
  if (cleaned.startsWith('0')) cleaned = cleaned.substring(1);
  return `+964${cleaned}`;
}

// دالة إرسال الرمز
window.sendOTP = async function(phoneNumber) {
  try {
    window.initRecaptcha();
    const formattedPhone = formatIraqiPhone(phoneNumber);
    const appVerifier = window.recaptchaVerifier;
    
    const confirmationResult = await signInWithPhoneNumber(auth, formattedPhone, appVerifier);
    window.confirmationResult = confirmationResult;
    alert("تم إرسال رمز التحقق بنجاح إلى: " + formattedPhone);
    return true;
  } catch (error) {
    console.error("خطأ بالإرسال:", error);
    alert("حدث خطأ في الإرسال: " + error.message);
    return false;
  }
};

// دالة التأكد من الرمز
window.verifyOTP = async function(code) {
  try {
    const result = await window.confirmationResult.confirm(code);
    alert("تم التوثيق بنجاح! أهلاً بك " + result.user.phoneNumber);
    return result.user;
  } catch (error) {
    alert("الرمز غير صحيح!");
    return null;
  }
};

