import os
import json
import asyncio
import base58

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey

BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing")

if not PRIVATE_KEY:
    raise ValueError("SOLANA_PRIVATE_KEY is missing")

private_key_str = PRIVATE_KEY.strip()

if private_key_str.startswith("["):
    keypair = Keypair.from_bytes(bytes(json.loads(private_key_str)))
else:
    keypair = Keypair.from_bytes(base58.b58decode(private_key_str))

wallet_address = str(keypair.pubkey())
client = Client("https://api.mainnet-beta.solana.com")


def get_sol_balance():
    resp = client.get_balance(Pubkey.from_string(wallet_address))
    lamports = resp.value
    return lamports / 1_000_000_000


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Проверить баланс", callback_data="balance")],
        [InlineKeyboardButton("Panic перевод", callback_data="panic_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выбери действие:",
        reply_markup=reply_markup
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "balance":
        try:
            sol_balance = get_sol_balance()
            text = (
                f"Wallet:\n{wallet_address}\n\n"
                f"SOL: {sol_balance:.6f}"
            )
            await query.edit_message_text(text)
        except Exception as e:
            await query.edit_message_text(f"Ошибка чтения баланса:\n{str(e)}")

    elif query.data == "panic_menu":
        keyboard = [
            [InlineKeyboardButton("Сейчас", callback_data="panic_now")],
            [InlineKeyboardButton("Через 5 минут", callback_data="panic_5")],
            [InlineKeyboardButton("Через 15 минут", callback_data="panic_15")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Когда выполнить перевод?",
            reply_markup=reply_markup
        )

    elif query.data == "panic_now":
        await query.edit_message_text("Перевод скоро добавим")

    elif query.data == "panic_5":
        await query.edit_message_text("Перевод через 5 минут")
        await asyncio.sleep(300)

    elif query.data == "panic_15":
        await query.edit_message_text("Перевод через 15 минут")
        await asyncio.sleep(900)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()


if __name__ == "__main__":
    main()
