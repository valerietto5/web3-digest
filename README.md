# Web3 Digest Wallet CLI

A small, DB-backed crypto wallet toolkit:

- Stores **balance snapshots** (what you own)
- Stores **price snapshots** (market prices)
- Computes a **portfolio report** (totals + per-asset values + honest 24h deltas)
- Prints everything via a **CLI** (Command Line Interface)

Docs:
- Vision: `VISION.md`
- Shipped: `SHIPPED.md`
- Roadmap: `ROADMAP.md`
- Technical deep dive: `TECHNICAL_DEEP_DIVE.md`

---

## Solana demo flow (recommended)

Fastest way to test the Solana read-only wallet end-to-end. It reads from `accounts.json`:
- wallet address
- default assets list

Run:
run_solana_demo.bat sol-test usd

What it does (3 steps):
1) **Balances snapshot (on-chain)**
   - Pulls SOL + SPL token balances from Solana RPC
   - Writes rows into `balance_snapshots`

2) **Prices snapshot (market)**
   - Pulls prices from CoinGecko (SOL/USDC/etc.)
   - Uses DexScreener fallback for allowlisted SPL mints (USD only)
   - Writes rows into `price_snapshots`

3) **Wallet report**
   - Reads latest balance + price snapshots from SQLite
   - Computes totals + per-asset values + honest 24h deltas
   - Prints the CLI report

Notes on 24h deltas:
- 24h change only appears when a baseline snapshot exists near "24h ago" (within a 30h tolerance).
- If you run daily (or roughly daily) snapshots, 24h deltas become reliable.

---

## Demo (manual engine flow)

Shortcut:
run_demo.bat

Or run step-by-step:

1) Update balances (manual snapshot):
python run_balances_to_db.py --account val-main --assets btc eth --set btc=0.01 eth=0.2 --no-report

2) Update prices (CoinGecko snapshot):
python run_prices_to_db.py --assets btc eth --currency usd --quiet

3) View wallet report:
python wallet_cli.py --account val-main --currency usd --assets btc eth

---

## Wallet UX (saved accounts)

List saved accounts:
python wallet_cli.py --list-accounts

Run using an account's default assets (from `accounts.json`):
python wallet_cli.py --account sol-test --currency usd

Save/update an account:
python wallet_cli.py --save-account sol-test2 --address <PUBKEY> --chain solana --assets sol usdc spl:<mint>

---

## Swap entry (V0 redirect)

This does NOT swap inside our app. It prints a Jupiter swap link you can open in your browser.

Swap SOL -> USDC:
python wallet_cli.py --swap-from sol --swap-to usdc

Swap SOL -> USDC using a saved account (also prints the account address):
python wallet_cli.py --account sol-test --swap-from sol --swap-to usdc

---

## Notes

- Local files like `wallet.db`, `exports/`, and `.venv/` are ignored via `.gitignore`.
- This project is V0 (non-custodial): no private keys, no signing, no seed phrase handling.