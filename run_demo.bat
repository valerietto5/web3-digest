@echo off
REM Demo flow: update balances -> update prices -> show wallet

python run_balances_to_db.py --account val-main --assets btc eth --set btc=0.01 eth=0.2 --no-report
python run_prices_to_db.py --assets btc eth --currency usd --quiet
python wallet_cli.py --account val-main --currency usd --assets btc eth
