import os
import json
import re
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
APIFY_TOKEN = os.environ["APIFY_TOKEN"]

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

SOURCES_FILE = "sources.json"
SEEN_FILE = "seen_posts.json"

# عدد المنشورات اللي نحاول نجيبها بالبداية
POST_LIMIT = 100


def load_json(filename, default):
    if not os.path.exists(filename):
        return default

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


def send_photo(photo_url, caption):
    response = requests.post(
        f"{TELEGRAM_API}/sendPhoto",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": photo_url,
            "caption": caption
        },
        timeout=40
    )

    response.raise_for_status()


def extract_username(url):
    """
    يحول:
    https://www.instagram.com/marsin_motors/
    إلى:
    marsin_motors
    """

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


def get_instagram_posts(username):
    """
    يستخدم Apify Actor لجلب المنشورات العامة.
    """

    actor_url = (
        "https://api.apify.com/v2/acts/"
        "steadyfetch~instagram-profile-posts/"
        "run-sync-get-dataset-items"
    )

    params = {
        "token": APIFY_TOKEN
    }

    payload = {
        "profiles": [
            username
        ],

        "resultsLimit": POST_LIMIT,

        "maxItems": POST_LIMIT,

        "maxRunSeconds": 900,

        "mediaType": "any"
    }

    print(f"🔎 Searching Instagram: @{username}")

    response = requests.post(
        actor_url,
        params=params,
        json=payload,
        timeout=1000
    )

    response.raise_for_status()

    data = response.json()

    print(
        f"📦 Received {len(data)} Instagram results"
    )

    return data


def get_post_id(post):
    """
    يحاول استخراج ID ثابت للمنشور.
    """

    for key in [
        "id",
        "shortCode",
        "shortcode",
        "postId",
        "pk"
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


def get_post_url(post):
    return (
        post.get("url")
        or post.get("postUrl")
        or post.get("permalink")
        or ""
    )


def get_caption(post):
    caption = (
        post.get("caption")
        or post.get("text")
        or post.get("description")
        or ""
    )

    return str(caption).strip()


def get_media_urls(post):
    """
    يحاول استخراج صور المنشور.
    """

    urls = []

    possible_fields = [
        "mediaUrls",
        "imageUrls",
        "images",
        "mediaAssets"
    ]

    for field in possible_fields:

        value = post.get(field)

        if not value:
            continue

        if isinstance(value, list):

            for item in value:

                if isinstance(item, str):
                    urls.append(item)

                elif isinstance(item, dict):

                    for key in [
                        "url",
                        "src",
                        "imageUrl",
                        "displayUrl"
                    ]:

                        if item.get(key):
                            urls.append(
                                item[key]
                            )

        elif isinstance(value, str):

            urls.append(value)

    # صور منفردة محتملة
    for key in [
        "displayUrl",
        "imageUrl",
        "thumbnailUrl",
        "thumbnail"
    ]:

        value = post.get(key)

        if value:
            urls.append(value)

    # إزالة التكرار
    result = []

    for url in urls:

        if url and url not in result:
            result.append(url)

    return result


def looks_like_car_ad(post):
    """
    فلتر أولي للإعلانات.
    ما نحاول نكون أذكى من اللازم بالبداية.
    """

    text = (
        get_caption(post)
        .lower()
    )

    car_keywords = [
        "سيارة",
        "سياره",
        "للبيع",
        "للبيع فقط",
        "موديل",
        "كيلو",
        "كم",
        "سعر",
        "مليون",
        "دولار",
        "toyota",
        "lexus",
        "bmw",
        "mercedes",
        "benz",
        "audi",
        "range rover",
        "land rover",
        "porsche",
        "ferrari",
        "lamborghini",
        "chevrolet",
        "ford",
        "gmc",
        "cadillac",
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
        "jeep"
    ]

    return any(
        keyword in text
        for keyword in car_keywords
    )


def format_post(post, source_url):
    caption = get_caption(post)
    post_url = get_post_url(post)

    username = (
        post.get("ownerUsername")
        or post.get("username")
        or extract_username(source_url)
        or "unknown"
    )

    timestamp = (
        post.get("timestamp")
        or post.get("takenAt")
        or post.get("date")
        or ""
    )

    text = (
        "🚗 IRAQ MOTORS - إعلان جديد\n\n"
        f"المعرض: @{username}\n\n"
        f"النص:\n{caption[:3000]}\n\n"
    )

    if timestamp:
        text += f"التاريخ: {timestamp}\n\n"

    if post_url:
        text += f"رابط المنشور:\n{post_url}\n\n"

    text += (
        "━━━━━━━━━━━━━━\n"
        "الحالة: يحتاج مراجعة يدوية"
    )

    return text


def process_source(source, seen_posts):

    source_url = source.get("url", "")

    if source.get("type") != "instagram":
        return

    username = extract_username(source_url)

    if not username:
        print(
            f"❌ Could not extract username: {source_url}"
        )
        return

    try:

        posts = get_instagram_posts(username)

    except Exception as e:

        print(
            f"❌ Instagram collector error: {e}"
        )

        return

    if not posts:
        print(
            f"⚠️ No posts found for @{username}"
        )

        return

    new_count = 0

    for post in posts:

        post_id = get_post_id(post)

        if not post_id:
            continue

        unique_id = (
            f"instagram:{username}:{post_id}"
        )

        if unique_id in seen_posts:
            continue

        caption = get_caption(post)

        # نخزن المنشور حتى لو مو إعلان سيارة
        # حتى ما نعيد فحصه كل مرة
        seen_posts[unique_id] = {
            "username": username,
            "post_id": post_id,
            "url": get_post_url(post),
            "first_seen": datetime.utcnow().isoformat()
        }

        if not looks_like_car_ad(post):
            print(
                f"⏭️ Skipped non-car post: {post_id}"
            )
            continue

        media_urls = get_media_urls(post)

        message = format_post(
            post,
            source_url
        )

        print(
            f"🚗 Car ad found: {post_id}"
        )

        try:

            if media_urls:

                # نرسل أول صورة ويا النص
                send_photo(
                    media_urls[0],
                    message
                )

                # إذا أكو صور إضافية
                for extra_photo in media_urls[1:10]:

                    try:

                        send_photo(
                            extra_photo,
                            "📸 صورة إضافية للإعلان"
                        )

                    except Exception as e:

                        print(
                            "⚠️ Extra photo failed:",
                            e
                        )

            else:

                send_message(message)

            new_count += 1

        except Exception as e:

            print(
                f"❌ Telegram error for {post_id}:",
                e
            )

    print(
        f"✅ @{username}: "
        f"{new_count} new car ads sent"
    )


def main():

    print("🚀 Iraq Motors Collector Started")

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
            "⚠️ No sources found in sources.json"
        )

        return

    print(
        f"📋 Sources: {len(sources)}"
    )

    for source in sources:

        try:

            process_source(
                source,
                seen_posts
            )

        except Exception as e:

            print(
                "❌ Source processing error:",
                e
            )

    save_json(
        SEEN_FILE,
        seen_posts
    )

    print(
        f"💾 Saved {len(seen_posts)} seen posts"
    )

    print(
        "🏁 Collector finished"
    )


if __name__ == "__main__":
    main()
