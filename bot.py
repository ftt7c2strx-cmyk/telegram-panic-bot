import os
import asyncio
import base58
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction

from spl.token.instructions import transfer_checked
from spl.token.instructions import TransferCheckedParams
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")
DESTINATION = os.getenv("DESTINATION_WALLET")

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

    await update.message.reply_text(
        "panic ready",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def panic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    delay = 300 if query.data == "panic5" else 900

    await query.edit_message_text("timer started")

    asyncio.create_task(panic_sequence(delay))


async def panic_sequence(delay):

    await asyncio.sleep(delay)

    await send_token(USDT_MINT)
    await asyncio.sleep(0.5)

    await send_token(USDC_MINT)
    await asyncio.sleep(0.5)

    await send_sol()


async def send_token(mint):

    owner = keypair.pubkey()

    source = get_associated_token_address(owner, mint)
    dest = get_associated_token_address(destination, mint)

    balance = await client.get_token_account_balance(source)

    if balance.value.amount == "0":
        return

    amount = int(balance.value.amount)

    decimals = balance.value.decimals

    tx = Transaction()

    tx.add(
        transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=source,
                mint=mint,
                dest=dest,
                owner=owner,
                amount=amount,
                decimals=decimals,
                signers=[],
            )
        )
    )

    await client.send_transaction(tx, keypair)


async def send_sol():

    balance = await client.get_balance(keypair.pubkey())

    lamports = balance.value - 5000

    if lamports <= 0:
        return

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


def main():

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(panic_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
