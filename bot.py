import os
import json
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SOURCES_FILE = "sources.json"


def load_sources():
    if not os.path.exists(SOURCES_FILE):
        return []

    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_sources(sources):
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def send_message(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


def get_updates(offset=None):
    params = {
        "timeout": 30
    }

    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        f"{API}/getUpdates",
        params=params,
        timeout=40
    )

    response.raise_for_status()
    return response.json()


def main():

    sources = load_sources()

    offset = None

    data = get_updates(offset)

    if not data.get("ok"):
        raise Exception(data)

    for update in data.get("result", []):

        offset = update["update_id"] + 1

        message = update.get("message")

        if not message:
            continue

        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        # /start
        if text == "/start":

            send_message(
                chat_id,
                "🚗 Iraq Motors Bot\n\n"
                "هلا بيك!\n\n"
                "الأوامر:\n"
                "/add - إضافة معرض\n"
                "/list - عرض المعارض\n"
                "/help - المساعدة"
            )

        # /help
        elif text == "/help":

            send_message(
                chat_id,
                "📖 طريقة الاستخدام:\n\n"
                "إضافة معرض:\n"
                "/add https://www.instagram.com/example/\n\n"
                "عرض المعارض:\n"
                "/list"
            )

        # /add
        elif text.startswith("/add"):

            parts = text.split(maxsplit=1)

            if len(parts) < 2:

                send_message(
                    chat_id,
                    "❌ لازم ترسل رابط المعرض بعد الأمر.\n\n"
                    "مثال:\n"
                    "/add https://www.instagram.com/marsin_motors/"
                )

                continue

            url = parts[1].strip()

            if not (
                "instagram.com" in url
                or "facebook.com" in url
            ):

                send_message(
                    chat_id,
                    "❌ حالياً أقبل روابط Instagram و Facebook فقط."
                )

                continue

            # منع التكرار
            if any(source["url"] == url for source in sources):

                send_message(
                    chat_id,
                    "⚠️ هذا المصدر مضاف مسبقاً."
                )

                continue

            source = {
                "url": url,
                "type": (
                    "instagram"
                    if "instagram.com" in url
                    else "facebook"
                )
            }

            sources.append(source)
            save_sources(sources)

            send_message(
                chat_id,
                "✅ تمت إضافة المصدر!\n\n"
                f"النوع: {source['type']}\n"
                f"الرابط:\n{url}"
            )

        # /list
        elif text == "/list":

            if not sources:

                send_message(
                    chat_id,
                    "📋 ماكو مصادر مضافة حالياً."
                )

                continue

            message_text = "📋 مصادر Iraq Motors:\n\n"

            for i, source in enumerate(sources, start=1):

                message_text += (
                    f"{i}. {source['type']}\n"
                    f"{source['url']}\n\n"
                )

            send_message(chat_id, message_text)


if __name__ == "__main__":
    main()
