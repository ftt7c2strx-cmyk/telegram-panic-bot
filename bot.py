import os
import asyncio
import base58
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")
DESTINATION = os.getenv("DESTINATION_WALLET")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

if not PRIVATE_KEY:
    raise ValueError("SOLANA_PRIVATE_KEY missing")

if not DESTINATION:
    raise ValueError("DESTINATION_WALLET missing")


RPC = "https://api.mainnet-beta.solana.com"

USDT_MINT = Pubkey.from_string("Es9vMFrzaCERd5Qf1J3LJ1mHh8VdNDo7Yw1sVn7kLPM")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wE9R8K3Ue1F")


client = AsyncClient(RPC)

keypair = Keypair.from_bytes(base58.b58decode(PRIVATE_KEY))

destination = Pubkey.from_string(DESTINATION)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("PANIC 5m", callback_data="panic5"),
            InlineKeyboardButton("PANIC 15m", callback_data="panic15"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Panic system ready", reply_markup=reply_markup)


async def panic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "panic5":
        delay = 300
    else:
        delay = 900

    await query.edit_message_text("Timer started")

    asyncio.create_task(panic_sequence(delay))


async def panic_sequence(delay: int):

    await asyncio.sleep(delay)

    await send_usdt()
    await asyncio.sleep(1)

    await send_usdc()
    await asyncio.sleep(1)

    await send_sol()


async def send_sol():

    lamports = 1000000

    tx = Transaction()

    tx.add(
        transfer(
            TransferParams(
                from_pubkey=keypair.pubkey(),
                to_pubkey=destination,
                lamports=lamports,
            )
        )
    )

    await client.send_transaction(tx, keypair)


async def send_usdt():
    # placeholder for token transfer
    pass


async def send_usdc():
    # placeholder for token transfer
    pass


def main():

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(panic_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
