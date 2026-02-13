# Web3 Digest Wallet CLI



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





## Notes

- 24h change is only shown when a baseline price snapshot exists near "24h ago" (within a 30h tolerance rule). Otherwise it prints `n/a`.

- Local files like `wallet.db` and `.venv/` are ignored via `.gitignore`.



