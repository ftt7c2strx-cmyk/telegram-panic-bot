import os
import json
import asyncio
import base58
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,
    ConversationHandler
)

from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.commitment_config import CommitmentLevel
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import (
    transfer as spl_transfer,
    TransferParams as SplTransferParams,
    create_associated_token_account,
    get_associated_token_address,
)
from spl.token.client import Token

# -------------------- CONFIGURATION --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")
DESTINATION_WALLET = os.getenv("DESTINATION_WALLET")
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing")
if not PRIVATE_KEY:
    raise ValueError("SOLANA_PRIVATE_KEY is missing")
if not DESTINATION_WALLET:
    raise ValueError("DESTINATION_WALLET is missing")

# Parse private key (supports both base58 and array formats)
private_key_str = PRIVATE_KEY.strip()
if private_key_str.startswith("["):
    keypair = Keypair.from_bytes(bytes(json.loads(private_key_str)))
else:
    keypair = Keypair.from_bytes(base58.b58decode(private_key_str))

wallet_address = str(keypair.pubkey())
client = Client(RPC_URL)

# Token mint addresses (Solana mainnet)
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

# -------------------- HELPER FUNCTIONS --------------------
def get_sol_balance() -> float:
    resp = client.get_balance(keypair.pubkey(), commitment=Confirmed)
    return resp.value / 1_000_000_000

def get_token_balance(mint_str: str) -> float:
    """Return total UI balance of a given mint for the wallet."""
    mint = Pubkey.from_string(mint_str)
    accounts = client.get_token_accounts_by_owner(
        keypair.pubkey(),
        {"mint": mint},
        commitment=Confirmed
    ).value
    total = 0.0
    for acc in accounts:
        total += acc.account.data.parsed['info']['tokenAmount']['uiAmount']
    return total

def ensure_associated_token_account(dest_wallet: Pubkey, mint: Pubkey) -> Pubkey:
    """Create ATA for destination if it doesn't exist, return its address."""
    ata = get_associated_token_address(dest_wallet, mint)
    # Check if ATA exists
    try:
        client.get_account_info(ata, commitment=Confirmed)
        return ata  # already exists
    except:
        # Create ATA
        txn = create_associated_token_account(keypair.pubkey(), dest_wallet, mint)
        client.send_transaction(txn, keypair, opts=TxOpts(skip_preflight=True))
        # Wait a bit for confirmation
        asyncio.sleep(2)
        return ata

def transfer_sol(dest: Pubkey, amount_lamports: int):
    """Send lamports to destination."""
    txn = transfer(
        TransferParams(
            from_pubkey=keypair.pubkey(),
            to_pubkey=dest,
            lamports=amount_lamports
        )
    )
    client.send_transaction(txn, keypair, opts=TxOpts(skip_preflight=True))

def transfer_spl_token(mint: Pubkey, source_token_account: Pubkey, dest_wallet: Pubkey, amount_raw: int):
    """Transfer SPL tokens from source to destination's ATA (creates ATA if needed)."""
    dest_ata = ensure_associated_token_account(dest_wallet, mint)
    txn = spl_transfer(
        SplTransferParams(
            program_id=TOKEN_PROGRAM_ID,
            source=source_token_account,
            dest=dest_ata,
            owner=keypair.pubkey(),
            amount=amount_raw,
            signers=[]  # keypair is the owner, no extra signers
        )
    )
    client.send_transaction(txn, keypair, opts=TxOpts(skip_preflight=True))

def emergency_transfer():
    """Transfer all USDT, then USDC, then SOL to destination wallet."""
    dest_pubkey = Pubkey.from_string(DESTINATION_WALLET)

    # 1. Transfer USDT
    usdt_mint = Pubkey.from_string(USDT_MINT)
    usdt_accounts = client.get_token_accounts_by_owner(
        keypair.pubkey(),
        {"mint": usdt_mint},
        commitment=Confirmed
    ).value
    for acc in usdt_accounts:
        token_account = acc.pubkey
        balance_raw = acc.account.data.parsed['info']['tokenAmount']['amount']
        if int(balance_raw) > 0:
            transfer_spl_token(usdt_mint, token_account, dest_pubkey, int(balance_raw))

    # 2. Transfer USDC
    usdc_mint = Pubkey.from_string(USDC_MINT)
    usdc_accounts = client.get_token_accounts_by_owner(
        keypair.pubkey(),
        {"mint": usdc_mint},
        commitment=Confirmed
    ).value
    for acc in usdc_accounts:
        token_account = acc.pubkey
        balance_raw = acc.account.data.parsed['info']['tokenAmount']['amount']
        if int(balance_raw) > 0:
            transfer_spl_token(usdc_mint, token_account, dest_pubkey, int(balance_raw))

    # 3. Transfer SOL (leave 0.001 SOL for fees)
    sol_balance_lamports = client.get_balance(keypair.pubkey(), commitment=Confirmed).value
    transfer_lamports = sol_balance_lamports - 1_000_000  # leave 0.001 SOL
    if transfer_lamports > 0:
        transfer_sol(dest_pubkey, transfer_lamports)

# -------------------- BOT HANDLERS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security check will be added later by user
    keyboard = [
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance")],
        [InlineKeyboardButton("🚨 Panic Transfer", callback_data="panic_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose action:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "balance":
        try:
            sol = get_sol_balance()
            usdc = get_token_balance(USDC_MINT)
            usdt = get_token_balance(USDT_MINT)
            text = (
                f"📊 Your Balances:\n"
                f"SOL: {sol:.4f}\n"
                f"USDC: {usdc:.2f}\n"
                f"USDT: {usdt:.2f}\n\n"
                f"Wallet: `{wallet_address}`"
            )
            await query.edit_message_text(text, parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"❌ Error reading balances:\n{str(e)}")

    elif query.data == "panic_menu":
        keyboard = [
            [InlineKeyboardButton("⏱️ Now", callback_data="panic_now")],
            [InlineKeyboardButton("⏱️ 5 minutes", callback_data="panic_5")],
            [InlineKeyboardButton("⏱️ 15 minutes", callback_data="panic_15")],
            [InlineKeyboardButton("◀️ Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select delay:", reply_markup=reply_markup)

    elif query.data == "back":
        await start(update, context)  # Re-send main menu

    elif query.data == "panic_now":
        await query.edit_message_text("🚀 Executing transfer now...")
        asyncio.create_task(do_transfer(context, query.message.chat_id))

    elif query.data == "panic_5":
        await query.edit_message_text("⏳ Transfer scheduled in 5 minutes. Use /cancel to abort.")
        context.user_data['timer'] = 300
        context.user_data['cancelled'] = False
        asyncio.create_task(delayed_transfer(context, query.message.chat_id, 300))

    elif query.data == "panic_15":
        await query.edit_message_text("⏳ Transfer scheduled in 15 minutes. Use /cancel to abort.")
        context.user_data['timer'] = 900
        context.user_data['cancelled'] = False
        asyncio.create_task(delayed_transfer(context, query.message.chat_id, 900))

async def delayed_transfer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, delay: int):
    await asyncio.sleep(delay)
    if context.user_data.get('cancelled', False):
        await context.bot.send_message(chat_id, "❌ Scheduled transfer cancelled.")
        return
    await do_transfer(context, chat_id)

async def do_transfer(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        await context.bot.send_message(chat_id, f"🔄 Transferring funds to `{DESTINATION_WALLET}` in order: USDT → USDC → SOL...")
        emergency_transfer()
        await context.bot.send_message(chat_id, "✅ Emergency transfer completed successfully!")
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Transfer failed: {str(e)}")
        logging.exception("Transfer error")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security check will be added later
    context.user_data['cancelled'] = True
    await update.message.reply_text("Cancelled any scheduled transfer.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    main()
