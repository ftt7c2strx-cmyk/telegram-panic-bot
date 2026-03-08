import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")


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
        await query.edit_message_text("Баланс кошелька (добавим позже)")

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
        await query.edit_message_text("Перевод будет выполнен сейчас (скоро добавим)")

    elif query.data == "panic_5":
        await query.edit_message_text("Перевод через 5 минут")

        await asyncio.sleep(300)

        print("PANIC TRANSFER EXECUTED")

    elif query.data == "panic_15":
        await query.edit_message_text("Перевод через 15 минут")

        await asyncio.sleep(900)

        print("PANIC TRANSFER EXECUTED")


def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()


if __name__ == "__main__":
    main()
