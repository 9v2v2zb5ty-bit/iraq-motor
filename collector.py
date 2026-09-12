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
# LOAD JSON
# =========================================================

def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================================================
# CAR FILTER
# =========================================================

CAR_KEYWORDS = [
    # Arabic
    "سيارة",
    "سياره",
    "للبيع",
    "بيع",
    "للبيع حصرا",
    "للبیع",
    "سعر",
    "موديل",
    "موديل",
    "موديلها",
    "مواصفات",
    "وارد",
    "وارد امريكي",
    "وارد أمريكي",
    "وارد خليجي",
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
    "رقم",
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

    # Brands
    "toyota",
    "lexus",
    "land cruiser",
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
    caption = str(post.get("caption") or "").lower()

    hashtags = post.get("hashtags") or []

    if isinstance(hashtags, list):
        hashtag_text = " ".join(str(x) for x in hashtags).lower()
    else:
        hashtag_text = str(hashtags).lower()

    text = f"{caption} {hashtag_text}"

    for keyword in CAR_KEYWORDS:
        if keyword.lower() in text:
            return True

    return False


# =========================================================
# SOURCE HANDLING
# =========================================================

def normalize_instagram_username(url):
    url = url.strip().rstrip("/")

    if "instagram.com/" in url:
        username = url.split("instagram.com/")[-1]
        username = username.split("/")[0]
        return username

    return url.replace("@", "")


def load_sources():
    sources = load_json(SOURCES_FILE, [])

    if not sources:
        print("⚠️ No sources found in sources.json")
        return []

    return sources


# =========================================================
# APIFY PROFILE SCRAPER
# =========================================================

def run_profile_actor(username):

    payload = {
        "profiles": [username],
        "resultsLimit": POST_LIMIT,
        "maxItems": POST_LIMIT,
        "maxRunSeconds": 1800,
        "mediaType": "any"
    }

    headers = {
        "Content-Type": "application/json"
    }

    for attempt in range(1, 4):

        print(f"🔄 Profile Apify attempt {attempt}/3")

        try:

            response = requests.post(
                PROFILE_ACTOR,
                params={"token": APIFY_TOKEN},
                json=payload,
                headers=headers,
                timeout=600
            )

            print(
                f"📡 Apify profile HTTP status: "
                f"{response.status_code}"
            )

            if response.status_code == 201:

                data = response.json()

                if not isinstance(data, list):
                    print("⚠️ Unexpected Apify response")
                    return []

                return data

            print(
                f"⚠️ Apify returned: "
                f"{response.text[:500]}"
            )

        except Exception as e:
            print(f"❌ Apify profile error: {e}")

        time.sleep(5)

    return []


# =========================================================
# APIFY POST MEDIA SCRAPER
# =========================================================

def run_media_actor(post_urls):

    if not post_urls:
        return {}

    print(
        f"📸 Enriching {len(post_urls)} posts "
        f"to retrieve ALL carousel media..."
    )

    payload = {
        "postUrls": post_urls,
        "maxItems": len(post_urls)
    }

    headers = {
        "Content-Type": "application/json"
    }

    for attempt in range(1, 4):

        print(f"🔄 Media Apify attempt {attempt}/3")

        try:

            response = requests.post(
                POST_ACTOR,
                params={"token": APIFY_TOKEN},
                json=payload,
                headers=headers,
                timeout=900
            )

            print(
                f"📡 Apify media HTTP status: "
                f"{response.status_code}"
            )

            if response.status_code == 201:

                data = response.json()

                if not isinstance(data, list):
                    print("⚠️ Unexpected media response")
                    return {}

                result = {}

                for item in data:

                    if not isinstance(item, dict):
                        continue

                    shortcode = (
                        item.get("shortCode")
                        or item.get("shortcode")
                    )

                    url = item.get("url")

                    key = shortcode or url

                    if key:
                        result[key] = item

                print(
                    f"📦 Media details received: "
                    f"{len(result)} posts"
                )

                return result

            print(
                f"⚠️ Media actor response: "
                f"{response.text[:500]}"
            )

        except Exception as e:
            print(f"❌ Apify media error: {e}")

        time.sleep(5)

    return {}


# =========================================================
# EXTRACT ALL IMAGES
# =========================================================

def extract_all_media(post):

    media = []

    # -----------------------------------------------------
    # 1. images array
    # -----------------------------------------------------

    images = post.get("images")

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
                )

                if url:
                    media.append({
                        "type": "image",
                        "url": url
                    })

    # -----------------------------------------------------
    # 2. childPosts
    # -----------------------------------------------------

    children = post.get("childPosts")

    if isinstance(children, list):

        for child in children:

            if not isinstance(child, dict):
                continue

            child_type = str(
                child.get("type") or ""
            ).lower()

            image_url = (
                child.get("displayUrl")
                or child.get("image")
            )

            video_url = child.get("videoUrl")

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
    # 3. displayUrl fallback
    # -----------------------------------------------------

    if not media:

        display_url = post.get("displayUrl")

        if display_url:

            media.append({
                "type": "image",
                "url": display_url
            })

    # -----------------------------------------------------
    # 4. video fallback
    # -----------------------------------------------------

    if not media:

        video_url = post.get("videoUrl")

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

        url = item.get("url")

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)
        unique.append(item)

    return unique


# =========================================================
# TELEGRAM
# =========================================================

def telegram_send_message(text):

    url = f"{TELEGRAM_API}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }

    response = requests.post(
        url,
        json=payload,
        timeout=60
    )

    return response.ok


def telegram_send_album(media_items, caption):

    """
    Telegram media group maximum = 10 items.
    So 12 photos become 10 + 2.
    """

    if not media_items:
        return False

    success = True

    # Telegram supports max 10 media items per group
    chunks = [
        media_items[i:i + 10]
        for i in range(0, len(media_items), 10)
    ]

    first_chunk = True

    for chunk in chunks:

        media = []

        for index, item in enumerate(chunk):

            media_type = item["type"]
            media_url = item["url"]

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

            # Caption only on first item
            if first_chunk and index == 0:
                obj["caption"] = caption
                obj["parse_mode"] = "HTML"

            media.append(obj)

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
                    "❌ Telegram album error:",
                    response.text[:500]
                )

                success = False

        except Exception as e:

            print(
                f"❌ Telegram album exception: {e}"
            )

            success = False

        first_chunk = False

        # Small delay between chunks
        if len(chunks) > 1:
            time.sleep(1)

    return success


# =========================================================
# FORMAT TELEGRAM CAPTION
# =========================================================

def escape_html(text):

    text = str(text or "")

    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_caption(post):

    caption = post.get("caption") or ""

    post_url = post.get("url") or ""

    username = (
        post.get("ownerUsername")
        or post.get("profileHandle")
        or ""
    )

    taken_at = post.get("takenAt") or ""

    carousel_count = post.get("carouselCount")

    text = (
        "🚗 <b>Iraq Motors - إعلان جديد</b>\n\n"
        f"👤 الحساب: @{escape_html(username)}\n"
    )

    if taken_at:
        text += (
            f"🕒 التاريخ: "
            f"{escape_html(taken_at)}\n"
        )

    if carousel_count:
        text += (
            f"📸 الصور: {carousel_count}\n"
        )

    text += "\n"

    if caption:

        # Telegram caption limit
        safe_caption = escape_html(caption)

        if len(safe_caption) > 800:
            safe_caption = safe_caption[:800] + "..."

        text += safe_caption
        text += "\n\n"

    if post_url:
        text += (
            f'🔗 <a href="{post_url}">'
            "فتح المنشور على Instagram"
            "</a>"
        )

    return text


# =========================================================
# MAIN
# =========================================================

def main():

    print("🚀 Iraq Motors Collector Started")

    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN missing")
        return

    if not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID missing")
        return

    if not APIFY_TOKEN:
        print("❌ APIFY_TOKEN missing")
        return

    sources = load_sources()

    print(
        f"📋 Sources: {len(sources)}"
    )

    seen_posts = set(
        load_json(SEEN_FILE, [])
    )

    all_new_car_posts = []

    # =====================================================
    # COLLECT FROM ALL SOURCES
    # =====================================================

    for source in sources:

        source_url = source.get("url")

        if not source_url:
            continue

        username = normalize_instagram_username(
            source_url
        )

        print(
            f"\n🔍 Processing @{username}"
        )

        raw_items = run_profile_actor(
            username
        )

        print(
            f"📦 Raw items received: "
            f"{len(raw_items)}"
        )

        actual_posts = []

        for item in raw_items:

            if not isinstance(item, dict):
                continue

            status = item.get("status")

            if status in [
                "profile",
                "run_summary"
            ]:

                print(
                    "ℹ️ صف مو بوست "
                    f"(بروفايل/ملخص) — "
                    f"status={status}"
                )

                continue

            post_id = (
                item.get("postId")
                or item.get("id")
                or item.get("shortCode")
            )

            post_url = item.get("url")

            if not post_id and not post_url:
                continue

            actual_posts.append(item)

        print(
            f"🚗 Actual posts found: "
            f"{len(actual_posts)}"
        )

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
        # FILTER
        # -------------------------------------------------

        new_candidates = []

        for post in actual_posts:

            post_id = (
                post.get("postId")
                or post.get("id")
                or post.get("shortCode")
            )

            if not post_id:
                continue

            if str(post_id) in seen_posts:
                continue

            if not looks_like_car_ad(post):

                print(
                    f"⏭️ Not a car ad: "
                    f"{post_id}"
                )

                # We mark it seen too, so it doesn't
                # get checked forever.
                seen_posts.add(str(post_id))

                continue

            print(
                f"🚗 Car ad found: "
                f"{post_id}"
            )

            new_candidates.append(post)

        all_new_car_posts.extend(
            new_candidates
        )

    # =====================================================
    # MEDIA ENRICHMENT
    # =====================================================

    print(
        f"\n🚗 New car ads requiring processing: "
        f"{len(all_new_car_posts)}"
    )

    if not all_new_car_posts:

        save_json(
            SEEN_FILE,
            sorted(seen_posts)
        )

        print(
            f"💾 Saved {len(seen_posts)} seen posts"
        )

        print("🏁 Collector finished")
        return

    post_urls = []

    for post in all_new_car_posts:

        url = post.get("url")

        if url:
            post_urls.append(url)

    media_details = run_media_actor(
        post_urls
    )

    # =====================================================
    # SEND TO TELEGRAM
    # =====================================================

    sent_count = 0

    for post in all_new_car_posts:

        post_id = (
            post.get("postId")
            or post.get("id")
            or post.get("shortCode")
        )

        post_url = post.get("url")

        shortcode = (
            post.get("shortCode")
            or post.get("shortcode")
        )

        # Find enriched media row
        enriched = None

        if shortcode:
            enriched = media_details.get(
                shortcode
            )

        if enriched is None and post_url:
            enriched = media_details.get(
                post_url
            )

        if enriched is None:
            enriched = post

        media_items = extract_all_media(
            enriched
        )

        print(
            f"📸 Images found for "
            f"{post_id}: {len(media_items)}"
        )

        if not media_items:

            print(
                f"⚠️ No media found: "
                f"{post_id}"
            )

            # Fallback to original display URL
            display_url = post.get(
                "displayUrl"
            )

            if display_url:

                media_items = [{
                    "type": "image",
                    "url": display_url
                }]

        if not media_items:

            print(
                f"❌ Cannot send "
                f"{post_id}, no media"
            )

            # Mark as seen to avoid endless retries
            seen_posts.add(str(post_id))

            continue

        caption = build_caption(post)

        success = telegram_send_album(
            media_items,
            caption
        )

        if success:

            sent_count += 1

            seen_posts.add(
                str(post_id)
            )

            print(
                f"✅ Sent: {post_id} "
                f"({len(media_items)} media)"
            )

        else:

            print(
                f"❌ Failed to send: "
                f"{post_id}"
            )

        time.sleep(1)

    # =====================================================
    # SAVE SEEN
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

    print("🏁 Collector finished")


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
