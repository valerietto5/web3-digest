# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python application centered on wallet reporting and Solana swap transparency. Most core modules live at the repo root: `db.py` manages SQLite storage, `portfolio.py` builds reports, and helpers such as `solana_rpc.py`, `token_registry.py`, and `wallet_helpers.py` support chain- and token-specific logic. The FastAPI app lives in `api/`, with `api/main.py` exposing JSON endpoints and `/ui`, and `api/ui_page.py` serving the inline HTML UI. Tests are currently minimal and live in `test_sanity.py`. Local runtime data includes `wallet.db`, `accounts.json`, `balances.json`, and `exports/`.

## Build, Test, and Development Commands
Create a virtual environment and install dependencies with `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
Run the API locally with `uvicorn api.main:app --reload`; the UI is then available at `http://127.0.0.1:8000/ui`.
Run the CLI with `python3 wallet_cli.py --account val-main`.
Refresh local data with scripts such as `python3 run_balances_to_db.py`, `python3 run_prices_to_db.py`, and `python3 run_portfolio_history.py`.
Run tests with `python3 -m unittest test_sanity.py`.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, snake_case for functions and variables, PascalCase for test classes, and explicit imports over wildcard imports. Keep modules focused and top-level scripts named by action, for example `run_prices_to_db.py` or `inspect_db.py`. There is no configured formatter or linter in the repo today, so match the surrounding style closely and keep changes narrow.

## Testing Guidelines
Use `unittest`, mirroring `test_sanity.py`. Prefer isolated tests that create a temporary SQLite database with `tempfile` instead of touching `wallet.db`. Name new tests `test_*.py`, and name methods by behavior, such as `test_get_price_at_or_before_returns_latest_match`.

## Commit & Pull Request Guidelines
Recent history mixes descriptive commits with generic uploads; prefer short, imperative commit messages like `Add swap fee fallback handling` or `Fix Mac DB path resolution`. Keep one logical change per commit. PRs should include a concise summary, affected commands or endpoints, linked issues if any, and screenshots for `/ui` changes.

## Security & Configuration Tips
Do not commit `accounts.json`, `.env`, SQLite files, WAL files, or generated exports. Use `accounts.sample.json` as the template for local account setup, and treat local wallet addresses, API keys, and devnet transaction data as sensitive.
