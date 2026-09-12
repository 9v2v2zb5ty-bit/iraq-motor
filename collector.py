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

APIFY_ACTOR_URL = (
    "https://api.apify.com/v2/acts/"
    "steadyfetch~instagram-profile-posts/"
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
            f"⚠️ Failed to read {filename}: {e}"
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


def send_photo(
    photo_url,
    caption=None
):

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

        "maxRunSeconds": 900,

        "mediaType": "any"
    }

    headers = {

        "Content-Type":
            "application/json",

        "Accept":
            "application/json",

        "User-Agent":
            "IraqMotorsCollector/1.0"
    }

    max_attempts = 3

    for attempt in range(
        1,
        max_attempts + 1
    ):

        try:

            print(
                f"🔄 Apify attempt "
                f"{attempt}/{max_attempts}"
            )

            response = requests.post(

                APIFY_ACTOR_URL,

                params={
                    "token": APIFY_TOKEN
                },

                json=payload,

                headers=headers,

                timeout=1200
            )

            print(
                f"📡 Apify HTTP status: "
                f"{response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(
                data,
                list
            ):

                print(
                    "⚠️ Apify returned "
                    "unexpected data format"
                )

                print(
                    str(data)[:2000]
                )

                return []

            print(
                f"📦 Received "
                f"{len(data)} posts"
            )

            return data

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout
        ) as e:

            print(
                f"⚠️ Apify connection "
                f"failed: {e}"
            )

            if attempt < max_attempts:

                wait_time = attempt * 10

                print(
                    f"⏳ Waiting "
                    f"{wait_time} seconds..."
                )

                time.sleep(
                    wait_time
                )

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
                f"❌ Unexpected Apify error: {e}"
            )

            return []

    print(
        "❌ Apify failed after "
        "all attempts"
    )

    return []


# =========================================================
# POST ID
# =========================================================

def get_post_id(post):

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

    caption = (

        post.get("caption")

        or post.get("text")

        or post.get("description")

        or ""

    )

    return str(
        caption
    ).strip()


# =========================================================
# IMAGE EXTRACTION
# =========================================================

def get_media_urls(post):

    urls = []


    def add_url(value):

        if not value:

            return


        # URL مباشرة

        if isinstance(
            value,
            str
        ):

            if (

                value.startswith("http")

                and value not in urls

            ):

                urls.append(value)

            return


        # Dictionary

        if isinstance(
            value,
            dict
        ):

            for key in [

                "url",
                "src",
                "imageUrl",
                "displayUrl",
                "display_url",
                "image_url",
                "thumbnailUrl",
                "thumbnail"

            ]:

                if value.get(key):

                    add_url(
                        value.get(key)
                    )


    # =====================================================
    # MULTIPLE IMAGES
    # =====================================================

    for key in [

        "images",
        "imageUrls",
        "mediaUrls",
        "mediaAssets",
        "children",
        "childPosts",
        "carousel",
        "sidecar"

    ]:

        value = post.get(key)


        if isinstance(
            value,
            list
        ):

            for item in value:

                add_url(item)


        elif isinstance(
            value,
            dict
        ):

            for item in value.values():

                add_url(item)


    # =====================================================
    # MAIN IMAGE
    # =====================================================

    for key in [

        "displayUrl",
        "imageUrl",
        "thumbnailUrl",
        "thumbnail",
        "display_url"

    ]:

        add_url(
            post.get(key)
        )


    # =====================================================
    # INSTAGRAM EDGE STRUCTURES
    # =====================================================

    for key in [

        "edge_sidecar_to_children",
        "edge_media_to_caption",
        "edge_media_preview"

    ]:

        value = post.get(key)


        if isinstance(
            value,
            dict
        ):

            edges = value.get(
                "edges"
            )


            if isinstance(
                edges,
                list
            ):

                for edge in edges:

                    if isinstance(
                        edge,
                        dict
                    ):

                        node = edge.get(
                            "node"
                        )

                        if node:

                            add_url(
                                node
                            )


    # =====================================================
    # REMOVE DUPLICATES
    # =====================================================

    unique_urls = []

    for url in urls:

        if url not in unique_urls:

            unique_urls.append(url)

    return unique_urls


# =========================================================
# CAR FILTER
# =========================================================

def looks_like_car_ad(post):

    text = get_caption(
        post
    ).lower()

    car_keywords = [

        "سيارة",
        "سياره",
        "للبيع",
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
        "defender",

        "porsche",
        "ferrari",
        "lamborghini",

        "chevrolet",
        "corvette",
        "tahoe",

        "ford",
        "mustang",
        "raptor",

        "gmc",
        "yukon",

        "kia",
        "hyundai",
        "nissan",

        "chery",
        "jetour",
        "geely",
        "haval",
        "mg",

        "dodge",
        "charger",
        "challenger",

        "jeep",
        "wrangler"

    ]

    return any(
        keyword in text
        for keyword in car_keywords
    )


# =========================================================
# FORMAT MESSAGE
# =========================================================

def format_post(
    post,
    source_url
):

    caption = get_caption(
        post
    )

    post_url = get_post_url(
        post
    )

    username = (

        post.get(
            "ownerUsername"
        )

        or post.get(
            "username"
        )

        or extract_username(
            source_url
        )

        or "unknown"

    )

    timestamp = (

        post.get(
            "timestamp"
        )

        or post.get(
            "takenAt"
        )

        or post.get(
            "date"
        )

        or ""

    )


    text = (

        "🚗 IRAQ MOTORS\n\n"

        f"المعرض: @{username}\n\n"

        "📝 الإعلان:\n"

        f"{caption[:3000]}\n\n"

    )


    if timestamp:

        text += (

            f"📅 التاريخ: "
            f"{timestamp}\n\n"

        )


    if post_url:

        text += (

            "🔗 رابط المنشور:\n"

            f"{post_url}\n\n"

        )


    text += (

        "━━━━━━━━━━━━━━\n"

        "⏳ يحتاج مراجعة يدوية"

    )

    return text


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
            f"❌ Invalid Instagram URL: "
            f"{source_url}"
        )

        return


    posts = get_instagram_posts(
        username
    )


    if not posts:

        print(
            f"⚠️ No posts returned "
            f"for @{username}"
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


        # =================================================
        # DUPLICATE CHECK
        # =================================================

        if unique_id in seen_posts:

            continue


        # =================================================
        # SAVE AS SEEN
        # =================================================

        seen_posts[
            unique_id
        ] = {

            "username":
                username,

            "post_id":
                post_id,

            "url":
                get_post_url(
                    post
                ),

            "first_seen":
                datetime.utcnow().isoformat()

        }


        # =================================================
        # CAR FILTER
        # =================================================

        if not looks_like_car_ad(
            post
        ):

            print(
                f"⏭️ Not a car ad: "
                f"{post_id}"
            )

            continue


        # =================================================
        # IMAGES
        # =================================================

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
            source_url
        )


        # =================================================
        # SEND TO TELEGRAM
        # =================================================

        try:

            if media_urls:

                # الصورة الأولى + معلومات الإعلان

                send_photo(
                    media_urls[0],
                    message
                )


                # باقي الصور

                for extra_photo in media_urls[1:15]:

                    try:

                        send_photo(
                            extra_photo,
                            "📸 صورة إضافية من نفس الإعلان"
                        )

                    except Exception as e:

                        print(
                            "⚠️ Failed to send "
                            f"extra image: {e}"
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
                f"❌ Source processing error: "
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
