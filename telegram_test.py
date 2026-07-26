from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ENABLED,
)
from telegram_bot.telegram_notifier import (
    TelegramNotifier,
)


def main() -> None:
    print("=" * 55)
    print("📨 AURUM TELEGRAM TESZT")
    print("=" * 55)

    telegram = TelegramNotifier(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        enabled=TELEGRAM_ENABLED,
    )

    if not TELEGRAM_ENABLED:
        print(
            "❌ A Telegram küldés ki van kapcsolva "
            "a .env fájlban."
        )
        return

    if not telegram.is_configured():
        print("❌ A Telegram nincs megfelelően beállítva.")
        print()
        print("Ellenőrizd ezt a fájlt:")
        print(r"C:\AURUM\.env")
        print()
        print("Szükséges értékek:")
        print("TELEGRAM_BOT_TOKEN=...")
        print("TELEGRAM_CHAT_ID=...")
        return

    result = telegram.send_test_message()

    if result["success"]:
        print("✅ A tesztüzenet elküldve.")
        print(
            "Telegram message ID: "
            f"{result.get('message_id')}"
        )
    else:
        print("❌ Nem sikerült elküldeni.")
        print(f"Hibakód: {result['code']}")
        print(f"Ok: {result['reason']}")


if __name__ == "__main__":
    main()