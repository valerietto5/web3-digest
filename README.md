# Web3 Digest Wallet CLI

Docs:
- Vision: VISION.md
- Shipped: SHIPPED.md
- Roadmap: ROADMAP.md
- Technical deep dive: TECHNICAL_DEEP_DIVE.md


A small, DB-backed crypto wallet toolkit:

- Stores balance snapshots (what you own)

- Stores price snapshots (market prices from CoinGecko)

- Prints a clean portfolio report via CLI (Command Line Interface)



## Demo (3-command flow)

Shortcut: run the full demo with:
run_demo.bat

1) Update balances (manual snapshot):
python run_balances_to_db.py --account val-main --assets btc eth --set btc=0.01 eth=0.2 --no-report

2) Update prices (CoinGecko snapshot):
python run_prices_to_db.py --assets btc eth --currency usd --quiet

3) View wallet report:
python wallet_cli.py --account val-main --currency usd --assets btc eth


## Wallet UX (saved accounts)

List saved accounts:
python wallet_cli.py --list-accounts

Run using an account's default assets (from accounts.json):
python wallet_cli.py --account sol-test --currency usd

Save a new account:
python wallet_cli.py --save-account sol-test2 --address <PUBKEY> --chain solana --assets sol usdc


## Swap entry (V0 redirect)

This does NOT swap inside our app. It prints a Jupiter swap link you can open in your browser.

Swap SOL → USDC:
python wallet_cli.py --swap-from sol --swap-to usdc

Swap SOL → USDC using a saved account (also prints the account address):
python wallet_cli.py --account sol-test --swap-from sol --swap-to usdc
## Notes

- 24h change is only shown when a baseline price snapshot exists near "24h ago" (within a 30h tolerance rule). Otherwise it prints `n/a`.

- Local files like `wallet.db` and `.venv/` are ignored via `.gitignore`.



