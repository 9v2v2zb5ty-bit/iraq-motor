import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


def main():
    response = requests.get(
        f"{API}/getUpdates",
        timeout=30
    )

    data = response.json()

    if not data.get("ok"):
        raise Exception(data)

    for update in data["result"]:
        message = update.get("message")

        if not message:
            continue

        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        if text == "/start":
            send_message(
                chat_id,
                "🚗 Iraq Motors Bot\n\n"
                "هلا بيك!\n\n"
                "الأوامر المتوفرة:\n"
                "/add - إضافة معرض\n"
                "/list - عرض المعارض\n"
                "/help - المساعدة"
            )


if __name__ == "__main__":
    main()
