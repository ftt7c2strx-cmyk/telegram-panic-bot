import os
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
from solders.keypair import Keypair

SEED_PHRASE = os.getenv("SEED_PHRASE")

if not SEED_PHRASE:
    raise ValueError("SEED_PHRASE not found")

# Генерируем seed из фразы
seed_bytes = Bip39SeedGenerator(SEED_PHRASE).Generate()

# Derivation path Solana
bip44 = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
account = bip44.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

private_key = account.PrivateKey().Raw().ToBytes()

# создаем keypair
kp = Keypair.from_seed(private_key[:32])

print(list(bytes(kp)))
print("Public address:", kp.pubkey())
