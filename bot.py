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

from spl.token.instructions import transfer_checked, TransferCheckedParams
from spl.token.instructions import get_associated_token_address
from spl.token.constants import TOKEN_PROGRAM_ID

logging.basicConfig(level=logging.INFO)


def get_env(name):
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} missing")
    return value.strip()


BOT_TOKEN = get_env("BOT_TOKEN")
PRIVATE_KEY = get_env("SOLANA_PRIVATE_KEY")
DESTINATION = get_env("DESTINATION_WALLET")


RPC = "https://api.mainnet-beta.solana.com"

USDT_MINT = Pubkey.from_string("Es9vMFrzaCERd5Qf1J3LJ1mHh8VdNDo7Yw1sVn7kLPM")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")


client = AsyncClient(RPC)


try:
    keypair = Keypair.from_bytes(base58.b58decode(PRIVATE_KEY))
except Exception as e:
    raise ValueError(f"SOLANA_PRIVATE_KEY invalid: {e}")


try:
    destination = Pubkey.from_string(DESTINATION)
except Exception as e:
    raise ValueError(f"DESTINATION_WALLET invalid: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [[
        InlineKeyboardButton("PANIC 5m", callback_data="panic5"),
        InlineKeyboardButton("PANIC 15m", callback_data="panic15")
    ]]

    await update.message.reply_text(
        "panic ready",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def panic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    delay = 300 if query.data == "panic5" else 900

    await query.edit_message_text("timer started")

    asyncio.create_task(panic_sequence(delay))


async def panic_sequence(delay):

    await asyncio.sleep(delay)

    owner = keypair.pubkey()

    tx = Transaction()

    await add_token_transfer(tx, owner, USDT_MINT)
    await add_token_transfer(tx, owner, USDC_MINT)

    balance = await client.get_balance(owner)

    lamports = balance.value - 5000

    if lamports > 0:

        tx.add(
            transfer(
                TransferParams(
                    from_pubkey=owner,
                    to_pubkey=destination,
                    lamports=lamports
                )
            )
        )

    await client.send_transaction(tx, keypair)


async def add_token_transfer(tx, owner, mint):

    try:

        source = get_associated_token_address(owner, mint)
        dest = get_associated_token_address(destination, mint)

        balance = await client.get_token_account_balance(source)

        if balance.value.amount == "0":
            return

        amount = int(balance.value.amount)
        decimals = balance.value.decimals

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
                    signers=[]
                )
            )
        )

    except Exception as e:
        logging.warning(f"Token transfer skipped: {e}")


def main():

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(panic_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
