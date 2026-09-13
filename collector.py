import os
import json
import re
import time
import requests
from datetime import datetime


# =========================================================
# SETTINGS
# =========================================================

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
APIFY_TOKEN = os.environ["APIFY_TOKEN"]

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

SOURCES_FILE = "sources.json"
SEEN_FILE = "seen_posts.json"

POST_LIMIT = 100

APIFY_URL = (
    "https://api.apify.com/v2/acts/"
    "steadyfetch~instagram-profile-posts/"
    "run-sync-get-dataset-items"
)

# أكتور ثاني مخصص لجلب *كل* صور منشور كاروسيل وحدة بوحدة (مو بس
# صورة الغلاف). نستخدم نفس APIFY_TOKEN — التوكن حساب كامل عند
# Apify، يشتغل مع أي أكتور، مو مربوط بأكتور وحدة.
CAROUSEL_ACTOR_URL = (
    "https://api.apify.com/v2/acts/"
    "memo23~instagram-post-scraper/"
    "run-sync-get-dataset-items"
)


# =========================================================
# JSON
# =========================================================

def load_json(filename, default):

    if not os.path.exists(filename):
        return default

    try:
        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception as e:

        print(
            f"⚠️ JSON read error: {e}"
        )

        return default


def save_json(filename, data):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# TELEGRAM
# =========================================================

def send_message(text):

    response = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        },
        timeout=30
    )

    response.raise_for_status()


def send_photo(photo_url, caption=None):

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url
    }

    if caption:
        data["caption"] = caption

    response = requests.post(
        f"{TELEGRAM_API}/sendPhoto",
        json=data,
        timeout=40
    )

    response.raise_for_status()


# =========================================================
# INSTAGRAM USERNAME
# =========================================================

def extract_username(url):

    match = re.search(
        r"instagram\.com/([^/?#]+)",
        url
    )

    if not match:
        return None

    username = match.group(1).strip()

    if username.startswith("@"):
        username = username[1:]

    return username


# =========================================================
# APIFY
# =========================================================

def get_instagram_posts(username):

    payload = {
        "profiles": [
            username
        ],

        "resultsLimit": POST_LIMIT,

        "maxItems": POST_LIMIT,

        "maxRunSeconds": 1800,

        "mediaType": "any",

        # مهم: هذا الأكتور عنده ذاكرة خاصة بحسابك بالـ Apify نفسه —
        # أي بوست "تسلّم" لحسابك بأي تشغيل سابق (حتى تجربة يدوية
        # جربتها بالكونسول قبل ما تربطه بـ GitHub Actions) ما يرجع
        # مرة ثانية إطلاقًا إلا إذا فعّلنا هالخيار. إحنا أصلاً عدنا
        # seen_posts.json نسوي فيه الفلترة بنفسنا، فنخلي الأكتور
        # يرجّعلنا كل شي يلگه ونتحكم إحنا بالتكرار محليًا.
        "includeSeen": True
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "IraqMotorsCollector/1.0"
    }

    for attempt in range(1, 4):

        try:

            print(
                f"🔄 Apify attempt "
                f"{attempt}/3"
            )

            response = requests.post(
                APIFY_URL,
                params={
                    "token": APIFY_TOKEN
                },
                json=payload,
                headers=headers,
                timeout=1900
            )

            print(
                f"📡 Apify HTTP status: "
                f"{response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list):

                print(
                    "❌ Apify returned "
                    "unexpected format"
                )

                print(
                    str(data)[:3000]
                )

                return []

            print(
                f"📦 Raw items received: "
                f"{len(data)}"
            )

            # ---------------------------------------------
            # هذا الأكتور (steadyfetch/instagram-profile-posts)
            # يحط بنفس الداتاسيت 3 أنواع صفوف مخلوطة سوا:
            #   1) صفوف بوستات حقيقية -> دايمًا فيها postId/shortCode + url
            #   2) صف واحد لكل بروفايل تطلبه -> status="profile" لو نجح،
            #      أو حالة فشل زي private_account/not_found/no_posts/
            #      rate_wall/rate_limited... لو فشل -> ما فيه postId
            #      ولا url إطلاقًا
            #   3) صف ملخص واحد للتشغيل كله -> نفس الشي، بلا postId
            # يعني "raw items" هميشة أكبر من عدد البوستات الفعلية بصف
            # أو صفين حتى لو رجعت صفر بوستات — هذا طبيعي مو خطأ.
            # نفلتر حسب وجود postId/url (هذا الفيصل الحقيقي بين بوست
            # وبين صف بروفايل/ملخص)، وأي صف نستبعده نطبع status/
            # statusReason حقّه عشان نعرف بالضبط ليش ما طلعت بوستات
            # إذا صارت هالحالة مرة ثانية.
            # ---------------------------------------------

            posts = []

            for item in data:

                if not isinstance(item, dict):
                    continue

                post_id = (
                    item.get("postId")
                    or item.get("id")
                    or item.get("shortCode")
                    or item.get("shortcode")
                )

                post_url = (
                    item.get("url")
                    or item.get("postUrl")
                    or item.get("permalink")
                )

                if post_id or post_url:

                    posts.append(item)

                else:

                    print(
                        "ℹ️ صف مو بوست (بروفايل/ملخص) — "
                        f"status={item.get('status') or '—'} | "
                        f"reason={item.get('statusReason') or '—'} | "
                        f"profile={item.get('profileHandle') or '—'} | "
                        f"postsReturned={item.get('postsReturned')}"
                    )

            print(
                f"🚗 Actual posts found: "
                f"{len(posts)}"
            )

            # عرض معلومات تشخيصية
            for i, post in enumerate(
                posts[:5],
                start=1
            ):

                print(
                    f"   {i}. "
                    f"{post.get('shortCode') or post.get('postId')} "
                    f"| type={post.get('type')} "
                    f"| status={post.get('status')} "
                    f"| carousel={post.get('carouselCount')}"
                )

            return posts

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout
        ) as e:

            print(
                f"⚠️ Connection error: {e}"
            )

            if attempt < 3:

                wait = attempt * 10

                print(
                    f"⏳ Waiting {wait} seconds..."
                )

                time.sleep(wait)

        except requests.exceptions.HTTPError as e:

            print(
                f"❌ Apify HTTP error: {e}"
            )

            print(
                response.text[:3000]
            )

            return []

        except Exception as e:

            print(
                f"❌ Apify error: {e}"
            )

            return []

    print(
        "❌ Apify failed after 3 attempts"
    )

    return []


# =========================================================
# POST ID
# =========================================================

def get_post_id(post):

    for key in [
        "postId",
        "id",
        "shortCode",
        "shortcode"
    ]:

        value = post.get(key)

        if value:
            return str(value)

    url = (
        post.get("url")
        or post.get("postUrl")
        or post.get("permalink")
    )

    if url:
        return url

    return None


# =========================================================
# POST URL
# =========================================================

def get_post_url(post):

    return (
        post.get("url")
        or post.get("postUrl")
        or post.get("permalink")
        or ""
    )


# =========================================================
# CAPTION
# =========================================================

def get_caption(post):

    value = (
        post.get("caption")
        or post.get("text")
        or post.get("description")
        or ""
    )

    return str(value).strip()


# =========================================================
# CAROUSEL (كل الصور)
# =========================================================

def get_carousel_slide_urls(post_url):

    # steadyfetch (أكتور البروفايل) ما يعطينا غير صورة الغلاف.
    # هذا أكتور ثاني (memo23/instagram-post-scraper) وظيفته يفتح
    # منشور وحدة برابطه ويرجع كل slide بالكاروسيل بصورته/فيديوه.
    # نستدعيه بس للمنشورات اللي عدّت فلتر إعلان السيارة (مو كل
    # البوستات) عشان ما ندفع مصاريف زيادة عالفاضي.

    payload = {
        "posts": [
            post_url
        ],

        "includeMediaUrls": True,
        "includeAuthorStats": False,
        "includeHashtagsMentions": False,
        "includeTaggedUsers": False
    }

    for attempt in range(1, 3):

        try:

            response = requests.post(
                CAROUSEL_ACTOR_URL,
                params={
                    "token": APIFY_TOKEN
                },
                json=payload,
                timeout=120
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list) or not data:
                return []

            item = data[0]

            # بوست خاص/محذوف/الرابط مو منشور -> بيرجع صف خطأ
            if item.get("error"):

                print(
                    f"⚠️ Carousel fetch failed for "
                    f"{post_url}: "
                    f"{item.get('message')}"
                )

                return []

            slides = item.get("slides") or []

            urls = []

            for slide in slides:

                url = (
                    slide.get("imageUrl")
                    or slide.get("videoUrl")
                )

                if url and url not in urls:
                    urls.append(url)

            return urls

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout
        ) as e:

            print(
                f"⚠️ Carousel fetch connection error: {e}"
            )

            if attempt < 2:
                time.sleep(5)

        except Exception as e:

            print(
                f"⚠️ Carousel fetch error: {e}"
            )

            return []

    print(
        f"⚠️ Carousel fetch failed after retries for "
        f"{post_url} — رح نكتفي بصورة الغلاف"
    )

    return []


# =========================================================
# IMAGES
# =========================================================

def get_media_urls(post):

    carousel_count = (
        post.get("carouselCount")
        or 1
    )

    post_type = post.get("type")

    # منشور كاروسيل بأكثر من صورة -> نجيب كل الصور من الأكتور الثاني
    if (
        post_type == "carousel"
        and carousel_count
        and carousel_count > 1
    ):

        post_url = get_post_url(post)

        if post_url:

            slide_urls = get_carousel_slide_urls(
                post_url
            )

            if slide_urls:
                return slide_urls

    # منشور صورة/فيديو مفرد، أو فشل جلب الكاروسيل الكامل -> نكتفي
    # بصورة الغلاف (displayUrl هو الحقل المؤكد من أكتور steadyfetch)
    display_url = post.get("displayUrl")

    return [display_url] if display_url else []


# =========================================================
# CAR FILTER
# =========================================================

def looks_like_car_ad(post):

    caption = get_caption(
        post
    ).lower()

    # إذا البوست carousel أو صورة،
    # نسمح له يدخل إذا بيه مؤشرات بيع سيارات.
    keywords = [

        # عربي
        "سيارة",
        "سياره",
        "سيارات",
        "للبيع",
        "بيع",
        "موديل",
        "كيلو",
        "كم",
        "سعر",
        "مليون",
        "دولار",

        # Brands
        "toyota",
        "lexus",
        "bmw",
        "mercedes",
        "benz",
        "audi",
        "porsche",
        "ferrari",
        "lamborghini",
        "chevrolet",
        "ford",
        "gmc",
        "kia",
        "hyundai",
        "nissan",
        "infiniti",
        "chery",
        "jetour",
        "geely",
        "haval",
        "mg",
        "dodge",
        "jeep",

        # Models
        "land cruiser",
        "prado",
        "camry",
        "corolla",
        "rav4",
        "patrol",
        "tahoe",
        "yukon",
        "suburban",
        "defender",
        "range rover",
        "wrangler",
        "mustang",
        "raptor",
        "corvette",
        "charger",
        "challenger",
        "911",
        "cayenne",
        "macan",
        "g63",
        "gle",
        "gls",
        "x5",
        "x6",
        "x7"
    ]

    return any(
        keyword in caption
        for keyword in keywords
    )


# =========================================================
# FORMAT
# =========================================================

def format_post(
    post,
    source_url,
    media_count=1
):

    caption = get_caption(
        post
    )

    post_url = get_post_url(
        post
    )

    username = (
        post.get("ownerUsername")
        or post.get("profileHandle")
        or post.get("username")
        or extract_username(source_url)
        or "unknown"
    )

    timestamp = (
        post.get("takenAt")
        or post.get("timestamp")
        or post.get("date")
        or ""
    )

    post_type = (
        post.get("type")
        or ""
    )

    carousel_count = (
        post.get("carouselCount")
        or 1
    )

    message = (
        "🚗 IRAQ MOTORS\n\n"
        f"🏪 المعرض: @{username}\n"
        f"📸 نوع المنشور: {post_type}\n"
        f"🖼️ عدد الصور بالمنشور الأصلي: {carousel_count}\n\n"
        "📝 الإعلان:\n"
        f"{caption[:3000]}\n\n"
    )

    if (
        carousel_count
        and carousel_count > 1
        and media_count < carousel_count
    ):

        message += (
            "📌 ملاحظة: گدرنا نجيب "
            f"{media_count} من {carousel_count} صورة بس — "
            "لباقي صور الألبوم افتح رابط المنشور.\n\n"
        )

    if timestamp:

        message += (
            f"📅 التاريخ: {timestamp}\n\n"
        )

    if post_url:

        message += (
            "🔗 رابط المنشور:\n"
            f"{post_url}\n\n"
        )

    message += (
        "━━━━━━━━━━━━━━\n"
        "⏳ يحتاج مراجعة يدوية"
    )

    return message


# =========================================================
# PROCESS SOURCE
# =========================================================

def process_source(
    source,
    seen_posts
):

    source_url = source.get(
        "url",
        ""
    )

    if source.get(
        "type"
    ) != "instagram":

        return

    username = extract_username(
        source_url
    )

    if not username:

        print(
            f"❌ Invalid URL: "
            f"{source_url}"
        )

        return

    posts = get_instagram_posts(
        username
    )

    if not posts:

        print(
            f"⚠️ No actual posts "
            f"found for @{username}"
        )

        return

    new_count = 0

    for post in posts:

        post_id = get_post_id(
            post
        )

        if not post_id:
            continue

        unique_id = (
            f"instagram:"
            f"{username}:"
            f"{post_id}"
        )

        # منع التكرار
        if unique_id in seen_posts:

            continue

        # نحفظ المنشور
        seen_posts[
            unique_id
        ] = {
            "username": username,
            "post_id": post_id,
            "url": get_post_url(post),
            "first_seen":
                datetime.utcnow().isoformat()
        }

        # فلترة السيارات
        if not looks_like_car_ad(
            post
        ):

            print(
                f"⏭️ Not a car ad: "
                f"{post_id}"
            )

            continue

        # استخراج الصور
        media_urls = get_media_urls(
            post
        )

        print(
            f"🚗 Car ad found: "
            f"{post_id}"
        )

        print(
            f"📸 Images found: "
            f"{len(media_urls)}"
        )

        message = format_post(
            post,
            source_url,
            len(media_urls)
        )

        try:

            if media_urls:

                # الصورة الأولى ويا معلومات الإعلان
                send_photo(
                    media_urls[0],
                    message
                )

                total = len(media_urls)

                # باقي صور الألبوم كلها (بلا سقف) — مرقّمة عشان
                # المراجع يعرف وين وصل، وياهن تأخير بسيط حتى ما
                # نصطدم برايت-لِمِت تليجرام لو الألبوم كبير
                for i, extra_photo in enumerate(
                    media_urls[1:],
                    start=2
                ):

                    try:

                        send_photo(
                            extra_photo,
                            f"📸 صورة {i}/{total}"
                        )

                        time.sleep(0.4)

                    except Exception as e:

                        print(
                            f"⚠️ Extra image error: "
                            f"{e}"
                        )

            else:

                send_message(
                    message
                )

            new_count += 1

        except Exception as e:

            print(
                f"❌ Telegram error "
                f"for {post_id}: {e}"
            )

    print(
        f"✅ @{username}: "
        f"{new_count} new car ads sent"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "🚀 Iraq Motors Collector Started"
    )

    sources = load_json(
        SOURCES_FILE,
        []
    )

    seen_posts = load_json(
        SEEN_FILE,
        {}
    )

    if not sources:

        print(
            "⚠️ No sources found "
            "in sources.json"
        )

        return

    print(
        f"📋 Sources: "
        f"{len(sources)}"
    )

    for source in sources:

        try:

            process_source(
                source,
                seen_posts
            )

        except Exception as e:

            print(
                f"❌ Source error: "
                f"{e}"
            )

    save_json(
        SEEN_FILE,
        seen_posts
    )

    print(
        f"💾 Saved "
        f"{len(seen_posts)} seen posts"
    )

    print(
        "🏁 Collector finished"
    )


if __name__ == "__main__":
    main()
