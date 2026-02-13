# Web3 Digest Wallet CLI

A small, DB-backed crypto wallet toolkit:
- Stores balance snapshots (what you own)
- Stores price snapshots (market prices from CoinGecko)
- Prints a clean portfolio report via CLI (Command Line Interface)

## Demo (3-command flow)

Shortcut: run the full demo with: run_demo.bat


1) Update balances (manual snapshot): python run_balances_to_db.py --account val-main --assets btc eth --set btc=0.01 eth=0.2 --no-report

2) Update prices (CoinGecko snapshot): python run_prices_to_db.py --assets btc eth --currency usd --quiet

3) View wallet report: python wallet_cli.py --account val-main --currency usd --assets btc eth

## Notes
- 24h change is only shown when a baseline price snapshot exists near "24h ago" (within a 30h tolerance rule). Otherwise it prints `n/a`.
- Local files like `wallet.db` and `.venv/` are ignored via `.gitignore`.

## Sample output

Example run: python wallet_cli.py --account val-main --currency usd --assets btc eth

Output: 
Account: val-main | Currency: usd
Generated: 2026-02-13T04:50:11.598021+00:00
Balances updated: just now | Prices updated: just now
Total: 1,052.05 usd
24h change: -11.43 usd (-1.07%)

Positions:
btc amt=0.01 px=66281 value=662.81 usd | 24h: -1.22%
eth amt=0.2 px=1946.21 value=389.24 usd | 24h: -0.83%


