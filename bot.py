import os
import json
import time
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
    except Exception:
        return []


def save_sources(sources):
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def send_message(chat_id, text):
    try:
        requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=30
        )
    except Exception as e:
        print("Send message error:", e)


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


def handle_message(message):
    sources = load_sources()

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    print(f"Received: {text}")

    # /start
    if text == "/start":
        send_message(
            chat_id,
            "🚗 Iraq Motors Bot\n\n"
            "هلا بيك!\n\n"
            "الأوامر المتوفرة:\n\n"
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
            return

        url = parts[1].strip()

        if not (
            "instagram.com" in url
            or "facebook.com" in url
        ):
            send_message(
                chat_id,
                "❌ حالياً أقبل روابط Instagram و Facebook فقط."
            )
            return

        if any(source["url"] == url for source in sources):
            send_message(
                chat_id,
                "⚠️ هذا المصدر مضاف مسبقاً."
            )
            return

        source_type = (
            "instagram"
            if "instagram.com" in url
            else "facebook"
        )

        source = {
            "url": url,
            "type": source_type
        }

        sources.append(source)
        save_sources(sources)

        send_message(
            chat_id,
            "✅ تمت إضافة المصدر!\n\n"
            f"النوع: {source_type}\n"
            f"الرابط:\n{url}"
        )

    # /list
    elif text == "/list":

        if not sources:
            send_message(
                chat_id,
                "📋 ماكو مصادر مضافة حالياً."
            )
            return

        message_text = "📋 مصادر Iraq Motors:\n\n"

        for i, source in enumerate(sources, start=1):
            message_text += (
                f"{i}. {source['type']}\n"
                f"{source['url']}\n\n"
            )

        send_message(chat_id, message_text)

    else:
        send_message(
            chat_id,
            "❓ أمر غير معروف.\n\n"
            "استخدم /help حتى تشوف الأوامر."
        )


def main():

    print("🚀 Iraq Motors Telegram Bot started!")

    offset = None

    while True:

        try:

            data = get_updates(offset)

            if not data.get("ok"):
                print("Telegram API error:", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):

                offset = update["update_id"] + 1

                message = update.get("message")

                if message:
                    handle_message(message)

        except requests.exceptions.RequestException as e:

            print("Network error:", e)
            time.sleep(5)

        except Exception as e:

            print("Unexpected error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
