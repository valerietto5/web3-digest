# Technical Deep Dive

## Layer 1 — System Map
### 1) External APIs & Protocols
### 2) Data Ingestion
### 3) Normalization & Registries
### 4) Persistence (SQLite)
### 5) Portfolio Compute
### 6) Wallet UX (CLI)
### 7) Project/Docs + Generated/Legacy

## Layer 2 — File Map (grouped by Layer 1)
(we’ll fill in file-by-file)


### 1) External APIs & Protocols

This project touches the outside world in **three** places:

#### A) CoinGecko — price snapshots (HTTPS REST)
- **What it is:** a public HTTP API that returns JSON price data.
- **Where we use it:** `wallet_helpers.py`
- **Main function:** `fetch_prices(coins, currency="usd")`
  - Calls: `https://api.coingecko.com/api/v3/simple/price`
  - Input: internal asset keys like `btc`, `eth`, `sol`, `usdc`, or allowlisted `spl:<mint>`
  - Output: a `{asset_key: price}` mapping that gets written into SQLite via `run_prices_to_db.py`.

#### B) Solana mainnet RPC — on-chain balances (HTTPS JSON-RPC)
- **What it is:** Solana nodes expose a **JSON-RPC** interface over HTTPS (request/response JSON).
- **Where we use it:** `providers/solana_rpc.py`
- **Main functions:**
  - `_rpc_call(...)` — low-level helper that sends a JSON-RPC request and returns parsed JSON.
  - `get_sol_balance_lamports(address)` — reads native SOL balance (in lamports).
  - `get_spl_token_balances(address)` — reads SPL token accounts and returns UI amounts.
- **Default endpoint:** `https://api.mainnet-beta.solana.com`
- **Important:** this is **read-only**. We do not sign transactions, and we do not handle seed phrases.

#### C) Jupiter swap link — redirect only (no API call)
- **What it is:** a URL that opens Jupiter’s swap UI in a browser.
- **Where we use it:** `wallet_cli.py`
- **Behavior:** when you pass `--swap-from` and `--swap-to`, we print a link like:
  - `https://jup.ag/swap/SOL-USDC`
- **Important:** we are **not swapping inside our app** (V0 policy). This is a “wallet-like escape hatch”.



### 2) Data Ingestion

*Goal:* pull raw balances + prices from the outside world and write *snapshots* into SQLite so the rest of the system can compute/report.

#### Balance ingestion (what you own → balance_snapshots)
- *run_balances_to_db.py* (CLI entrypoint)
  - Manual mode: --set btc=0.01 eth=0.2
  - Solana mode: --source solana --address <PUBKEY>
  - Writes snapshot via db.insert_balance_snapshot(...)
- *providers/solana_balance_provider.py* (adapter/bridge)
  - Converts Solana wallet → dict like:
    - {"sol": 0.0058, "usdc": 0.0, "spl:<mint>": 123.45, ...}
  - Keeps the DB format consistent with the wallet engine
- *providers/solana_rpc.py* (low-level RPC client)
  - Fetches SOL balance (lamports → SOL)
  - Fetches SPL token balances (token accounts → ui amounts)

*Key functions / blocks (balances)*
- normalize_asset_key(...) — keeps asset keys consistent (especially spl:<mint> casing rules).
- parse_set_kv(...) — parses --set key=value pairs into a dict.
- main(...) — parses args, selects source (manual vs solana), inserts snapshot, optional report.

#### Price ingestion (market prices → price_snapshots)
- *run_prices_to_db.py* (CLI entrypoint)
  - Fetches prices for requested assets/currency
  - Writes snapshot via db.insert_price_snapshot(...)
- *wallet_helpers.py* (CoinGecko client + mapping)
  - fetch_prices(...) calls CoinGecko Simple Price API
  - coingecko_id_for_asset(...) maps our asset keys to CoinGecko ids (including allowlisted SPL cases)

*Key functions / blocks (prices)*
- main(...) — parses args (--assets, --currency, --quiet, --limit), fetches prices, inserts snapshot.

#### Demo convenience
- *run_demo.bat*
  - Runs the demo sequence:
    1) balances → 2) prices → 3) wallet_cli.py
  - Note: it’s a .bat script (no Python def, so it won’t show in findstr "def ")

#### Derived ingestion (portfolio history — upcoming)
- *run_portfolio_history.py*
  - Calls compute_portfolio_report(...)
  - Writes a “portfolio snapshot” time series into a history table (once finalized)

#### What ingestion does not do
It does *not* compute wallet logic (totals, deltas, staleness decisions).  
That happens in:
- *Portfolio Compute:* portfolio.py
- *Wallet UX:* wallet_cli.py



### 3) Normalization & Registries

*Goal:* turn messy, source-specific identifiers (Solana mints, CoinGecko ids, mixed casing) into consistent “wallet asset keys” and human-friendly labels.

In this project, normalization makes these rules true:
- core assets are simple keys like sol, usdc, btc
- unknown Solana tokens use a stable format: spl:<mint>
- SPL mints remain *case-sensitive* (base58) — we never lowercase the mint
- display names use symbols (SOL/USDC/BONK) when known, otherwise shortened labels

*Files in this section:*

- *token_registry.py* (manual allowlist / registry)
  - *Purpose:* map SPL mint → metadata (symbol/name, and later pricing ids).
  - *Key functions:*
    - mint_to_asset_key(mint) — if mint is recognized, return a clean asset key (e.g. usdc), else return spl:<mint>.
    - asset_key_to_symbol(asset) — display helper (friendly symbol or shortened SPL label).

- *providers/solana_balance_provider.py* (chain → wallet key bridge)
  - *Purpose:* converts Solana RPC results into our normalized balance dict.
  - *Key function:*
    - fetch_solana_owner_balances(address) — returns { "sol": <amt>, "usdc": <amt>, "spl:<mint>": <amt>, ... } using the registry for known mints.

- *wallet_helpers.py* (pricing normalization + legacy helpers)
  - *Purpose (relevant here):* normalize pricing inputs so CoinGecko queries work with our asset keys.
  - *Key functions (normalization-related):*
    - coingecko_id_for_asset(asset) — maps internal asset keys to CoinGecko ids (and supports allowlisted SPL cases).
    - norm(s) — normalizes generic input strings (used for currency and CLI parsing).
    - parse_coins(s, allowed=None) — parses/validates coin lists (legacy/CLI helper).

*Note:* wallet_helpers.py also contains older helpers for local JSON snapshots (save_snapshot, load_snapshots) and manual balance files; those are not part of the main DB-backed V0 flow but remain useful for debugging/legacy paths



### 4) Persistence (SQLite)

*Goal:* store wallet state as durable snapshots so we can compute totals, history, and honest deltas later.

In V0, persistence is simple:
- we write *balance snapshots* (what you own) and *price snapshots* (market prices)
- we read back the *latest* values and small slices of *history*
- we support “baseline lookups” (ex: price at or before a timestamp) for 24h comparisons

*Files in this section:*

- *db.py* (database access layer)
  - *Purpose:* the single place where SQLite schema, inserts, and queries live.
  - *Why it exists:* keeps SQL and DB logic out of portfolio/CLI code; everything calls these functions.
  - *Key functions / blocks:*
    - get_conn(db_path=...) — opens a SQLite connection with sane defaults for local apps.
    - init_db(db_path=...) — creates tables if they don’t exist.
    - insert_price_snapshot(ts, prices, currency, source, ...) — writes rows into price_snapshots.
    - insert_balance_snapshot(ts, account, balances, source, ...) — writes rows into balance_snapshots.
    - get_latest_prices(...) / get_latest_prices_with_ts(...) — latest price per asset (optionally with timestamps).
    - get_latest_balances(...) / get_latest_balances_with_ts(...) — latest balance per asset (optionally with timestamps).
    - get_price_history(asset, currency, limit) — recent price history for one asset.
    - get_latest_price(asset, currency) / get_latest_balance(account, asset) — latest single value convenience helpers.
    - get_price_at_or_before(asset, currency, ts) — baseline lookup used for honest 24h deltas.
    - get_portfolio_value_history(...) — helper to retrieve historical portfolio values (used by history tooling).

- *wallet.db* (SQLite database file)
  - *Purpose:* local state storage (ignored by .gitignore).
  - *High-level tables:*
    - balance_snapshots — timestamped (ts, account, asset, amount, source)
    - price_snapshots — timestamped (ts, asset, currency, price, source)

- *inspect_db.py* (debug helper)
  - *Purpose:* quick inspection script for DB rows when debugging.
  - *Key functions:*
    - print_rows(rows, max_rows=20) — pretty prints a limited number of rows.
    - main() — entrypoint (connects/queries/prints depending on how you run it).



### 5) Portfolio Compute

*Goal:* combine the latest balances + latest prices into a wallet-grade portfolio report:
- per-asset positions (amount, price, value)
- totals
- honest deltas (previous snapshot and 24h baseline when available)
- “missing/stale” detection so we never lie

*Files in this section:*

- *portfolio.py* (domain logic / wallet engine)
  - *Purpose:* the “brain” of the wallet report. This is where we compute values and deltas using DB snapshots.
  - *Why it exists:* keeps wallet math reusable for CLI now and any future UI/API later.

  *Key functions / blocks:*
  - _baseline_ok(target_dt, baseline_ts) — validates whether a candidate baseline timestamp is “close enough” to the target (used for 24h tolerance rules).
  - _safe_pct(now_val, then_val) — safe percent-change helper (avoids divide-by-zero).
  - _normalize_price_row(row) — defensive helper to parse DB price rows into consistent (ts, price) format.
  - human_age(ts, now) — formats timestamps like “just now / 5 min ago / 2d 3h ago” for UX.
  - compute_portfolio_report(account, assets, currency="usd")
    - pulls latest balances for the account (via db.get_latest_balances_with_ts)
    - pulls latest prices for requested assets (via db.get_latest_prices_with_ts)
    - computes per-asset values and totals
    - computes “previous snapshot” deltas when available
    - computes 24h deltas using a baseline lookup (when available/valid)
    - returns a structured report object used by wallet_cli.py

*Important policy behavior:*
- If prices are stale or baseline data is missing, 24h change prints n/a (truthful reporting).



### 6) Wallet UX (CLI)

#### wallet_cli.py
**Purpose:** The “user-facing” entrypoint. Reads saved accounts, chooses assets, calls the portfolio engine, prints a clean report. Also provides wallet-like utilities (list accounts, save account, swap redirect link).

**Inputs:**
- CLI flags (`--account`, `--assets`, `--currency`, etc.)
- `accounts.json` (optional; used when `--account` is provided and `--assets` is omitted)
- SQLite DB (balances + prices snapshots)

**Outputs:**
- Console output (portfolio report)
- Optional side effects:
  - writes/updates `accounts.json` when using `--save-account`
  - prints swap redirect URL when using `--swap-from/--swap-to`

**Main dependencies:**
- `portfolio.compute_portfolio_report()` (domain report)
- `db.py` (via portfolio/db calls)
- `accounts.json` (saved accounts)

**How to run (examples):**
- `python wallet_cli.py --list-accounts`
- `python wallet_cli.py --account sol-test --currency usd`
- `python wallet_cli.py --account val-main --assets btc eth --currency usd`
- `python wallet_cli.py --swap-from sol --swap-to usdc`
- `python wallet_cli.py --account sol-test --swap-from sol --swap-to usdc`

#### accounts.json
**Purpose:** Saved “wallet profiles” so you don’t retype addresses/assets every time.

**Typical fields per account:**
- `chain` (e.g. `solana` or `manual`)
- `address` (Solana public key for read-only mode; null for manual)
- `default_assets` (assets used when `--assets` is not provided)

**Why it exists:** Makes the CLI feel like a wallet (saved accounts + defaults) instead of a one-off script.



### 7) Project / Docs + Generated / Legacy

*Goal:* give a “home” to everything that is not core wallet engine logic:
- documentation files
- repo configuration / dependencies
- local logs/config
- legacy scripts from older experiments
- generated folders (venv, pycache)

*Docs (project guidance)*
- README.md — how to run the demo, wallet UX commands, swap redirect usage, doc links.
- VISION.md — mission/vision/north star + V0/V1/V2 ladder + safety policy.
- ROADMAP.md — weekly/monthly plan + session logs.
- SHIPPED.md — high-level “what exists now” snapshot.
- TECHNICAL_DEEP_DIVE.md — this file (system map → file map → function glossary).
- LICENSE — licensing.

*Repo hygiene / dependencies*
- .gitignore — excludes .venv/, wallet.db, caches, etc.
- requirements.txt — Python dependencies.

*Generated folders (local only)*
- .venv/ — local Python virtual environment (not committed).
- __pycache__/ and providers/__pycache__/ — Python bytecode cache (not committed).

*Local config/log artifacts (non-core / debugging)*
- accounts.json — saved accounts (core to Wallet UX, but stored as user data).
- balances.json — older/manual balance file (legacy-ish).
- prices_log.jsonl — older logging for price tracking (legacy-ish).
- config.json, seen.json — used by digest.py (RSS tool).

*Legacy / side tools (not part of current wallet V0 pipeline)*
- digest.py — RSS ingestion tool (separate from wallet).  
  Key functions:
  - load_config, load_seen, save_seen
  - fetch_rss (reads RSS feeds)
  - filtering helpers (matches, parse_title, clean_text)
  - main() orchestrates the run
- price_tracker.py — older/side price tracking script (not core).
- vallets.py — typo/legacy file (not core).
- DB.Browser.for.SQLite-v3.13.1-win64.msi — optional GUI installer for DB browsing (not required for the code).
- Stray artifacts: ' and 3} — likely accidental files; safe to remove once confirmed unused.





## Layer 3 — Code Glossary (inside each file)
(we’ll list key functions/blocks alphabetically per file)

### Symbols / underscore (internal helpers)

- _baseline_ok(...) (portfolio.py) — checks whether a candidate baseline timestamp is “close enough” to the target (used for the 24h tolerance rule).
- _normalize_price_row(...) (portfolio.py) — defensive parser to turn a DB row into (ts, price) safely.
- _rpc_call(...) (providers/solana_rpc.py) — low-level Solana JSON-RPC request helper (POST + validate response).
- _safe_pct(now, then) (portfolio.py) — safe percent-change helper (returns None when division would be invalid).

### A

- asset_key_to_symbol(asset) (token_registry.py) — converts an internal asset key into a human-friendly label (especially for spl:<mint>).

### C

- clean_text(s) (digest.py) — cleans/normalizes text for matching (legacy RSS tool).
- coingecko_id_for_asset(asset) (wallet_helpers.py) — maps our internal asset keys to CoinGecko ids (supports allowlisted SPL cases).
- compute_portfolio_report(...) (portfolio.py) — core portfolio brain: balances + prices → positions/totals/deltas + missing/stale checks.
- currency_symbol(currency) (wallet_helpers.py) — returns a display symbol for a currency code (formatting helper).

### D

- display_asset(asset) (wallet_cli.py) — converts internal keys (sol, usdc, spl:<mint>) into CLI display labels (SOL/USDC/SPL:abcd…wxyz).

### F

- fetch_prices(coins, currency="usd") (wallet_helpers.py) — calls CoinGecko Simple Price API and returns prices keyed by the input assets.
- fetch_rss(...) (digest.py) — pulls jobs/items from RSS feeds (legacy tool).
- fetch_solana_owner_balances(address) (providers/solana_balance_provider.py) — reads SOL + SPL balances and returns normalized dict {sol/usdc/spl:<mint>: amount}.
- fmt_money(x, cur) (wallet_cli.py) — CLI money formatter (n/a if missing).
- fmt_money(amount, symbol="$") (wallet_helpers.py) — older/legacy money formatter (used outside wallet_cli).
- fmt_pct(x) (wallet_cli.py) — CLI percent formatter (n/a if missing).

### G

- get_cmd() (wallet_helpers.py) — helper for reading/normalizing a user command input (legacy interactive helpers).
- get_conn(...) (db.py) — opens a SQLite connection with sane defaults.
- get_latest_balance(...) (db.py) — latest (ts, amount) for one asset in one account.
- get_latest_balances(...) (db.py) — latest balances for a list of assets.
- get_latest_balances_with_ts(...) (db.py) — latest balances *including timestamps*.
- get_latest_price(...) (db.py) — latest (ts, price) for one asset.
- get_latest_prices(...) (db.py) — latest prices for a list of assets.
- get_latest_prices_with_ts(...) (db.py) — latest prices *including timestamps*.
- get_portfolio_value_history(...) (db.py) — reads historical portfolio values (used by history tooling).
- get_positive_amount(prompt) (wallet_helpers.py) — prompts for a positive numeric amount (legacy helper).
- get_price(data, coin, currency, default=None) (wallet_helpers.py) — extracts a single price from CoinGecko-style nested JSON.
- get_price_at_or_before(...) (db.py) — baseline lookup: find the nearest snapshot at/before a target time (crucial for 24h deltas).
- get_price_history(...) (db.py) — recent price history for one asset.
- get_sol_balance_lamports(address, ...) (providers/solana_rpc.py) — fetches SOL balance in lamports.
- get_spl_token_balances(address, ...) (providers/solana_rpc.py) — fetches SPL token accounts and returns mint + ui amount + decimals.
- get_wallet_name(prompt) (wallet_helpers.py) — prompts for a wallet/account name (legacy helper).

### H

- human_age(ts, now) (portfolio.py) — turns timestamps into friendly “x min ago / 2d 3h ago” strings for UX.

### I

- init_db(db_path=...) (db.py) — creates SQLite tables/indexes if missing.

- insert_balance_snapshot(ts, account, balances, source="manual", ...) (db.py) — inserts one balance snapshot (multiple rows, one per asset) into balance_snapshots.
- insert_price_snapshot(ts, prices, currency, source="coingecko", ...) (db.py) — inserts one price snapshot (multiple rows, one per asset) into price_snapshots.

### L

- load_accounts(path="accounts.json") (wallet_cli.py) — loads saved accounts from JSON (returns {} if file missing).
- load_config(path=CONFIG_PATH) (digest.py) — loads RSS tool configuration (legacy).
- load_seen(path=SEEN_PATH) (digest.py) — loads the “already seen” set for RSS tool (legacy).
- load_snapshots() (wallet_helpers.py) — loads legacy price snapshots from local JSON (older approach).

### M

- main(argv=None) (run_balances_to_db.py) — CLI entrypoint: choose source (manual/solana) → insert balance snapshot → optional report.
- main(argv=None) (run_prices_to_db.py) — CLI entrypoint: fetch CoinGecko prices → insert price snapshot → optional debug prints.
- main(argv=None) (wallet_cli.py) — CLI entrypoint: list/save accounts, swap redirect, or print wallet report.
- main() (run_portfolio_history.py) — runner for writing portfolio history snapshots (will expand as history table is implemented).
- main() (inspect_db.py) — DB inspection helper entrypoint.
- main() (digest.py) — RSS digest tool entrypoint (legacy).

- matches(job, cfg) (digest.py) — determines whether a job/item matches filter rules (legacy).

- mint_to_asset_key(mint) (token_registry.py) — converts SPL mint → internal asset key (usdc if known, else spl:<mint>).

### N

- norm(s) (wallet_helpers.py) — normalizes input strings (used for currency / parsing helpers).
- normalize_asset_key(s) (run_balances_to_db.py) — normalizes asset keys; preserves SPL mint case and standardizes prefixes.

### P

- parse_coins(s, allowed=None) (wallet_helpers.py) — parses/validates user coin lists (legacy helper).
- parse_set_kv(pairs) (run_balances_to_db.py) — parses --set key=value pairs into a balances dict.
- parse_title(title) (digest.py) — parses RSS job titles into structured fields (legacy).

- print_price(price, symbol="$", label="") (wallet_helpers.py) — prints price nicely (legacy helper).
- print_rows(rows, max_rows=20) (inspect_db.py) — prints DB rows with a limit (debugging helper).

### S

- safe_load_balances() (wallet_helpers.py) — loads balances from local file safely (legacy/manual mode).
- save_accounts(data, path="accounts.json") (wallet_cli.py) — writes saved accounts JSON to disk.
- save_balances(balances) (wallet_helpers.py) — saves balances to local file (legacy).
- save_seen(seen, path=SEEN_PATH) (digest.py) — saves seen-set for RSS tool (legacy).
- save_snapshot(prices, currency) (wallet_helpers.py) — saves legacy price snapshot locally (older approach).
- show_balances(balances) (wallet_helpers.py) — prints balances (legacy helper).

### T / U / V / W / Z

- (No project-defined functions starting with these letters in the current codebase.)
