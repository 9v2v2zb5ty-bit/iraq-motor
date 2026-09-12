import os
import json
import time
import requests

# =========================================================
# CONFIG
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

SOURCES_FILE = "sources.json"
SEEN_FILE = "seen_posts.json"

POST_LIMIT = 100

PROFILE_ACTOR = (
    "https://api.apify.com/v2/acts/"
    "steadyfetch~instagram-profile-posts/"
    "run-sync-get-dataset-items"
)

POST_ACTOR = (
    "https://api.apify.com/v2/acts/"
    "dami_studio~instagram-post-scraper/"
    "run-sync-get-dataset-items"
)

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
)


# =========================================================
# LOAD / SAVE JSON
# =========================================================

def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# CAR KEYWORDS
# =========================================================

CAR_KEYWORDS = [
    # Arabic
    "سيارة",
    "سياره",
    "للبيع",
    "بيع",
    "سعر",
    "موديل",
    "موديلها",
    "مواصفات",
    "وارد",
    "وارد امريكي",
    "وارد أمريكي",
    "وارد خليجي",
    "بغداد",
    "اربيل",
    "أربيل",
    "كربلاء",
    "البصرة",
    "نجف",
    "النجف",
    "دهوك",
    "سليمانية",
    "سعر السيارة",
    "للاستفسار",

    # English
    "for sale",
    "sale",
    "price",
    "model",
    "mileage",
    "km",
    "miles",
    "awd",
    "4wd",
    "v6",
    "v8",
    "v10",
    "v12",

    # Brands / models
    "toyota",
    "lexus",
    "land cruiser",
    "landcruiser",
    "prado",
    "camry",
    "corolla",
    "hilux",
    "rav4",
    "fortuner",

    "nissan",
    "patrol",
    "infiniti",

    "bmw",

    "mercedes",
    "benz",

    "audi",

    "porsche",

    "range rover",
    "land rover",
    "defender",

    "ford",
    "mustang",
    "raptor",

    "chevrolet",
    "corvette",

    "cadillac",
    "gmc",

    "dodge",
    "ram",

    "jeep",

    "chery",

    "kia",
    "hyundai",
    "genesis",

    "volkswagen",
    "volvo",
    "honda",
    "mazda",
    "subaru",
    "mitsubishi",
    "suzuki",

    "tesla",

    "ferrari",
    "lamborghini",
    "bentley",

    "rolls royce",
    "rolls-royce",

    "maserati",
    "aston martin",
    "mclaren",
]


def looks_like_car_ad(post):
    caption = str(
        post.get("caption") or ""
    ).lower()

    hashtags = post.get("hashtags") or []

    if isinstance(hashtags, list):
        hashtag_text = " ".join(
            str(x) for x in hashtags
        ).lower()
    else:
        hashtag_text = str(
            hashtags
        ).lower()

    text = (
        f"{caption} {hashtag_text}"
    )

    for keyword in CAR_KEYWORDS:
        if keyword.lower() in text:
            return True

    return False


# =========================================================
# INSTAGRAM USERNAME
# =========================================================

def normalize_instagram_username(url):

    url = str(url).strip().rstrip("/")

    if "instagram.com/" in url:

        username = (
            url.split("instagram.com/")[-1]
        )

        username = username.split("/")[0]

        return username

    return url.replace("@", "")


# =========================================================
# LOAD SOURCES
# =========================================================

def load_sources():

    sources = load_json(
        SOURCES_FILE,
        []
    )

    if not sources:

        print(
            "⚠️ No sources found in sources.json"
        )

        return []

    return sources


# =========================================================
# PROFILE APIFY
# =========================================================

def run_profile_actor(
    profile_url,
    username
):

    payload = {
        "profiles": [
            profile_url
        ],

        "resultsLimit": POST_LIMIT,

        "maxItems": POST_LIMIT,

        "maxRunSeconds": 1800,

        "mediaType": "any"
    }

    headers = {
        "Content-Type": "application/json"
    }

    # 5 محاولات
    for attempt in range(1, 6):

        print(
            f"🔄 Profile Apify attempt "
            f"{attempt}/5"
        )

        try:

            response = requests.post(
                PROFILE_ACTOR,

                params={
                    "token": APIFY_TOKEN
                },

                json=payload,

                headers=headers,

                timeout=900
            )

            print(
                "📡 Apify profile HTTP status: "
                f"{response.status_code}"
            )

            # -------------------------------------------------
            # HTTP ERROR
            # -------------------------------------------------

            if response.status_code != 201:

                print(
                    "⚠️ Apify HTTP error:"
                )

                print(
                    response.text[:1000]
                )

                time.sleep(15)

                continue

            # -------------------------------------------------
            # JSON
            # -------------------------------------------------

            try:

                data = response.json()

            except Exception:

                print(
                    "❌ Apify response "
                    "is not valid JSON"
                )

                time.sleep(15)

                continue

            if not isinstance(data, list):

                print(
                    "⚠️ Unexpected Apify response"
                )

                time.sleep(15)

                continue

            # -------------------------------------------------
            # COUNT REAL POSTS
            # -------------------------------------------------

            actual_posts = []

            for item in data:

                if not isinstance(item, dict):
                    continue

                status = item.get(
                    "status"
                )

                if status in [
                    "profile",
                    "run_summary"
                ]:
                    continue

                post_id = (
                    item.get("postId")
                    or item.get("id")
                    or item.get("shortCode")
                )

                post_url = item.get(
                    "url"
                )

                if post_id or post_url:

                    actual_posts.append(
                        item
                    )

            print(
                f"📦 Raw items received: "
                f"{len(data)}"
            )

            print(
                f"🚗 Actual posts found: "
                f"{len(actual_posts)}"
            )

            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            if actual_posts:

                return data

            # -------------------------------------------------
            # ZERO POSTS
            # -------------------------------------------------

            print(
                f"⚠️ Apify رجع 0 بوست "
                f"لـ @{username}"
            )

            print(
                "🔁 راح نعيد المحاولة..."
            )

            time.sleep(15)

        except Exception as e:

            print(
                f"❌ Apify profile error: "
                f"{e}"
            )

            time.sleep(15)

    print(
        f"❌ فشل قراءة @{username} "
        f"بعد 5 محاولات"
    )

    return []


# =========================================================
# POST MEDIA APIFY
# =========================================================

def run_media_actor(
    post_urls
):

    if not post_urls:

        return {}

    print(
        f"📸 Enriching "
        f"{len(post_urls)} posts "
        "to retrieve ALL carousel media..."
    )

    payload = {
        "postUrls": post_urls,

        "maxItems": len(post_urls)
    }

    headers = {
        "Content-Type": "application/json"
    }

    for attempt in range(1, 4):

        print(
            f"🔄 Media Apify attempt "
            f"{attempt}/3"
        )

        try:

            response = requests.post(
                POST_ACTOR,

                params={
                    "token": APIFY_TOKEN
                },

                json=payload,

                headers=headers,

                timeout=900
            )

            print(
                "📡 Apify media HTTP status: "
                f"{response.status_code}"
            )

            if response.status_code != 201:

                print(
                    "⚠️ Media actor error:"
                )

                print(
                    response.text[:1000]
                )

                time.sleep(10)

                continue

            try:

                data = response.json()

            except Exception:

                print(
                    "❌ Media response "
                    "is not valid JSON"
                )

                time.sleep(10)

                continue

            if not isinstance(data, list):

                print(
                    "⚠️ Unexpected media response"
                )

                return {}

            result = {}

            for item in data:

                if not isinstance(item, dict):
                    continue

                shortcode = (
                    item.get("shortCode")
                    or item.get("shortcode")
                )

                url = item.get(
                    "url"
                )

                key = (
                    shortcode
                    or url
                )

                if key:

                    result[key] = item

            print(
                f"📦 Media details received: "
                f"{len(result)} posts"
            )

            return result

        except Exception as e:

            print(
                f"❌ Apify media error: "
                f"{e}"
            )

            time.sleep(10)

    return {}


# =========================================================
# EXTRACT ALL MEDIA
# =========================================================

def extract_all_media(post):

    media = []

    # -----------------------------------------------------
    # images
    # -----------------------------------------------------

    images = post.get(
        "images"
    )

    if isinstance(images, list):

        for item in images:

            if isinstance(item, str):

                media.append({
                    "type": "image",
                    "url": item
                })

            elif isinstance(item, dict):

                url = (
                    item.get("url")
                    or item.get("displayUrl")
                    or item.get("src")
                )

                if url:

                    media.append({
                        "type": "image",
                        "url": url
                    })

    # -----------------------------------------------------
    # childPosts
    # -----------------------------------------------------

    children = post.get(
        "childPosts"
    )

    if isinstance(children, list):

        for child in children:

            if not isinstance(child, dict):
                continue

            image_url = (
                child.get("displayUrl")
                or child.get("image")
                or child.get("url")
            )

            video_url = child.get(
                "videoUrl"
            )

            if image_url:

                media.append({
                    "type": "image",
                    "url": image_url
                })

            elif video_url:

                media.append({
                    "type": "video",
                    "url": video_url
                })

    # -----------------------------------------------------
    # media
    # -----------------------------------------------------

    media_array = post.get(
        "media"
    )

    if isinstance(media_array, list):

        for item in media_array:

            if isinstance(item, str):

                media.append({
                    "type": "image",
                    "url": item
                })

            elif isinstance(item, dict):

                image_url = (
                    item.get("url")
                    or item.get("displayUrl")
                    or item.get("image")
                )

                video_url = item.get(
                    "videoUrl"
                )

                if image_url:

                    media.append({
                        "type": "image",
                        "url": image_url
                    })

                elif video_url:

                    media.append({
                        "type": "video",
                        "url": video_url
                    })

    # -----------------------------------------------------
    # displayUrl fallback
    # -----------------------------------------------------

    if not media:

        display_url = post.get(
            "displayUrl"
        )

        if display_url:

            media.append({
                "type": "image",
                "url": display_url
            })

    # -----------------------------------------------------
    # video fallback
    # -----------------------------------------------------

    if not media:

        video_url = post.get(
            "videoUrl"
        )

        if video_url:

            media.append({
                "type": "video",
                "url": video_url
            })

    # -----------------------------------------------------
    # REMOVE DUPLICATES
    # -----------------------------------------------------

    unique = []

    seen = set()

    for item in media:

        url = item.get(
            "url"
        )

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        unique.append(
            item
        )

    return unique


# =========================================================
# HTML ESCAPE
# =========================================================

def escape_html(text):

    text = str(
        text or ""
    )

    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# =========================================================
# BUILD TELEGRAM CAPTION
# =========================================================

def build_caption(post):

    caption = (
        post.get("caption")
        or ""
    )

    post_url = (
        post.get("url")
        or ""
    )

    username = (
        post.get("ownerUsername")
        or post.get("profileHandle")
        or ""
    )

    taken_at = (
        post.get("takenAt")
        or ""
    )

    carousel_count = post.get(
        "carouselCount"
    )

    text = (
        "🚗 <b>Iraq Motors - إعلان جديد</b>\n\n"
    )

    if username:

        text += (
            "👤 الحساب: @"
            f"{escape_html(username)}\n"
        )

    if taken_at:

        text += (
            "🕒 التاريخ: "
            f"{escape_html(taken_at)}\n"
        )

    if carousel_count:

        text += (
            f"📸 الصور: "
            f"{carousel_count}\n"
        )

    text += "\n"

    if caption:

        safe_caption = escape_html(
            caption
        )

        if len(safe_caption) > 800:

            safe_caption = (
                safe_caption[:800]
                + "..."
            )

        text += safe_caption

        text += "\n\n"

    if post_url:

        safe_url = escape_html(
            post_url
        )

        text += (
            f'<a href="{safe_url}">'
            "🔗 فتح المنشور على Instagram"
            "</a>"
        )

    return text


# =========================================================
# TELEGRAM ALBUM
# =========================================================

def telegram_send_album(
    media_items,
    caption
):

    if not media_items:

        return False

    # Telegram يسمح بحد أقصى 10 عناصر
    chunks = [
        media_items[i:i + 10]
        for i in range(
            0,
            len(media_items),
            10
        )
    ]

    success = True

    first_chunk = True

    for chunk in chunks:

        media = []

        for index, item in enumerate(
            chunk
        ):

            media_type = item.get(
                "type",
                "image"
            )

            media_url = item.get(
                "url"
            )

            if not media_url:
                continue

            if media_type == "video":

                obj = {
                    "type": "video",
                    "media": media_url
                }

            else:

                obj = {
                    "type": "photo",
                    "media": media_url
                }

            # الكابشن على أول صورة فقط
            if (
                first_chunk
                and index == 0
            ):

                obj["caption"] = caption

                obj["parse_mode"] = "HTML"

            media.append(
                obj
            )

        if not media:

            continue

        try:

            response = requests.post(
                f"{TELEGRAM_API}/sendMediaGroup",

                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "media": media
                },

                timeout=120
            )

            if not response.ok:

                print(
                    "❌ Telegram album error:"
                )

                print(
                    response.text[:1000]
                )

                success = False

        except Exception as e:

            print(
                f"❌ Telegram album exception: "
                f"{e}"
            )

            success = False

        first_chunk = False

        if len(chunks) > 1:

            time.sleep(2)

    return success


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "🚀 Iraq Motors Collector Started"
    )

    # -----------------------------------------------------
    # CHECK SECRETS
    # -----------------------------------------------------

    if not TELEGRAM_BOT_TOKEN:

        print(
            "❌ TELEGRAM_BOT_TOKEN missing"
        )

        return

    if not TELEGRAM_CHAT_ID:

        print(
            "❌ TELEGRAM_CHAT_ID missing"
        )

        return

    if not APIFY_TOKEN:

        print(
            "❌ APIFY_TOKEN missing"
        )

        return

    # -----------------------------------------------------
    # SOURCES
    # -----------------------------------------------------

    sources = load_sources()

    print(
        f"📋 Sources: {len(sources)}"
    )

    # -----------------------------------------------------
    # SEEN
    # -----------------------------------------------------

    seen_posts = set(
        str(x)
        for x in load_json(
            SEEN_FILE,
            []
        )
    )

    all_new_car_posts = []

    # =====================================================
    # PROCESS SOURCES
    # =====================================================

    for source in sources:

        source_url = source.get(
            "url"
        )

        if not source_url:

            continue

        username = (
            normalize_instagram_username(
                source_url
            )
        )

        print(
            f"\n🔍 Processing "
            f"@{username}"
        )

        # -------------------------------------------------
        # APIFY
        # -------------------------------------------------

        raw_items = run_profile_actor(
            source_url,
            username
        )

        # -------------------------------------------------
        # PROTECTION:
        # If Apify completely failed,
        # don't change seen_posts.
        # -------------------------------------------------

        if not raw_items:

            print(
                f"🛑 ما حصلنا أي بوستات "
                f"من @{username}"
            )

            print(
                "⏭️ تخطي المصدر بدون "
                "تغيير seen_posts"
            )

            continue

        # -------------------------------------------------
        # FILTER PROFILE/SUMMARY
        # -------------------------------------------------

        actual_posts = []

        for item in raw_items:

            if not isinstance(
                item,
                dict
            ):

                continue

            status = item.get(
                "status"
            )

            if status in [
                "profile",
                "run_summary"
            ]:

                reason = item.get(
                    "reason"
                )

                print(
                    "ℹ️ صف مو بوست "
                    f"(بروفايل/ملخص) — "
                    f"status={status}"
                )

                if reason:

                    print(
                        f"   ↳ {str(reason)[:500]}"
                    )

                continue

            post_id = (
                item.get("postId")
                or item.get("id")
                or item.get("shortCode")
            )

            post_url = item.get(
                "url"
            )

            if post_id or post_url:

                actual_posts.append(
                    item
                )

        print(
            f"🚗 Actual posts found: "
            f"{len(actual_posts)}"
        )

        # -------------------------------------------------
        # DEBUG FIRST 5
        # -------------------------------------------------

        for index, post in enumerate(
            actual_posts[:5],
            start=1
        ):

            print(
                f"   {index}. "
                f"{post.get('shortCode')} | "
                f"type={post.get('type')} | "
                f"status={post.get('status')} | "
                f"carousel={post.get('carouselCount')}"
            )

        # -------------------------------------------------
        # FILTER NEW POSTS
        # -------------------------------------------------

        for post in actual_posts:

            post_id = (
                post.get("postId")
                or post.get("id")
                or post.get("shortCode")
            )

            if not post_id:

                continue

            post_id = str(
                post_id
            )

            # -------------------------------------------------
            # DUPLICATE
            # -------------------------------------------------

            if post_id in seen_posts:

                print(
                    f"⏭️ Already seen: "
                    f"{post_id}"
                )

                continue

            # -------------------------------------------------
            # CAR FILTER
            # -------------------------------------------------

            if not looks_like_car_ad(
                post
            ):

                print(
                    f"⏭️ Not a car ad: "
                    f"{post_id}"
                )

                # Mark non-car post as seen
                seen_posts.add(
                    post_id
                )

                continue

            print(
                f"🚗 Car ad found: "
                f"{post_id}"
            )

            all_new_car_posts.append(
                post
            )

    # =====================================================
    # NEW POSTS COUNT
    # =====================================================

    print(
        "\n🚗 New car ads requiring "
        f"processing: {len(all_new_car_posts)}"
    )

    # -----------------------------------------------------
    # NOTHING NEW
    # -----------------------------------------------------

    if not all_new_car_posts:

        save_json(
            SEEN_FILE,
            sorted(seen_posts)
        )

        print(
            f"💾 Saved "
            f"{len(seen_posts)} seen posts"
        )

        print(
            "🏁 Collector finished"
        )

        return

    # =====================================================
    # GET POST URLS
    # =====================================================

    post_urls = []

    for post in all_new_car_posts:

        url = post.get(
            "url"
        )

        if url:

            post_urls.append(
                url
            )

    # =====================================================
    # MEDIA ENRICHMENT
    # =====================================================

    media_details = run_media_actor(
        post_urls
    )

    # =====================================================
    # SEND POSTS
    # =====================================================

    sent_count = 0

    for post in all_new_car_posts:

        post_id = (
            post.get("postId")
            or post.get("id")
            or post.get("shortCode")
        )

        post_id = str(
            post_id
        )

        post_url = post.get(
            "url"
        )

        shortcode = (
            post.get("shortCode")
            or post.get("shortcode")
        )

        # -------------------------------------------------
        # FIND ENRICHED DATA
        # -------------------------------------------------

        enriched = None

        if shortcode:

            enriched = media_details.get(
                shortcode
            )

        if (
            enriched is None
            and post_url
        ):

            enriched = media_details.get(
                post_url
            )

        # fallback
        if enriched is None:

            enriched = post

        # -------------------------------------------------
        # MEDIA
        # -------------------------------------------------

        media_items = extract_all_media(
            enriched
        )

        print(
            f"📸 Images found for "
            f"{post_id}: "
            f"{len(media_items)}"
        )

        # -------------------------------------------------
        # FALLBACK DISPLAY URL
        # -------------------------------------------------

        if not media_items:

            display_url = post.get(
                "displayUrl"
            )

            if display_url:

                media_items = [{
                    "type": "image",
                    "url": display_url
                }]

                print(
                    "📸 Using original "
                    "displayUrl fallback"
                )

        # -------------------------------------------------
        # NO MEDIA
        # -------------------------------------------------

        if not media_items:

            print(
                f"❌ Cannot send "
                f"{post_id}, "
                "no media"
            )

            # نخليه seen حتى ما يظل
            # يعيد نفس البوست كل 15 دقيقة
            seen_posts.add(
                post_id
            )

            continue

        # -------------------------------------------------
        # CAPTION
        # -------------------------------------------------

        caption = build_caption(
            post
        )

        # -------------------------------------------------
        # SEND
        # -------------------------------------------------

        success = telegram_send_album(
            media_items,
            caption
        )

        if success:

            sent_count += 1

            seen_posts.add(
                post_id
            )

            print(
                f"✅ Sent: "
                f"{post_id} "
                f"({len(media_items)} media)"
            )

        else:

            print(
                f"❌ Failed to send: "
                f"{post_id}"
            )

        time.sleep(1)

    # =====================================================
    # SAVE
    # =====================================================

    save_json(
        SEEN_FILE,
        sorted(seen_posts)
    )

    print(
        f"✅ New car ads sent: "
        f"{sent_count}"
    )

    print(
        f"💾 Saved "
        f"{len(seen_posts)} seen posts"
    )

    print(
        "🏁 Collector finished"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
