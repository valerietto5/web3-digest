
# Shipped (High-level)

This file is the quick “what exists right now” snapshot.
Updated weekly (and after major milestones).

## Current demo flows (work today)

### CLI (V0)
1) Insert balances (manual or Solana) → SQLite
2) Insert prices (CoinGecko + optional Dex fallback) → SQLite
3) Print wallet report (CLI)

### Web (V1 runway)
1) Open UI: `GET /ui`
2) Refresh balances: `POST /refresh/balances`
3) Refresh prices: `POST /refresh/prices` (Dex fallback supported)
4) View latest report + history: `GET /portfolio/latest`, `GET /portfolio/history`
5) Connect Phantom / disconnect / sign message
6) Attempt devnet Send SOL with transaction state UI
7) Run preflight balance checks before opening Phantom
8) View live devnet wallet balance
9) Request devnet airdrop from inside the UI (with diagnostics)
10) Review recent actions in the Activity Log

---

## Shipped milestones

### Phase 1 — Wallet engine + demo backbone ✅
- Balance snapshots (manual) → SQLite
- Price snapshots (CoinGecko) → SQLite
- Portfolio compute (positions + totals)
- Honest 24h deltas (30h tolerance rule)
- CLI wallet report

### Phase 2 — Solana read-only V0 ✅
- Solana RPC balance fetch:
  - SOL balance
  - SPL token balances (including Token-2022) with dust filter
- `run_balances_to_db.py --source solana --address <pubkey>` writes to `balance_snapshots`
- SPL policy Option 1:
  - unpriced SPL tokens grouped/hidden by default
  - `--show-unpriced` reveals full list

### Phase 3 — Token registry + SPL pricing ✅
- Added `token_registry.py`:
  - mint → `asset`, `symbol`, `name`, `coingecko_id`
- Solana balance normalization:
  - known mints → clean asset keys (for example `usdc`)
  - unknown mints → `spl:<mint>`
- SPL pricing support:
  - CoinGecko mapping for known tokens
  - DexScreener fallback (allowlist + minimum liquidity guard) for allowlisted SPL tokens (USD-only)
- Fixed mint case-sensitivity end-to-end:
  - no lowercasing SPL mints in balance inserts or price fetch

### Phase 4 — Wallet UX V0 (CLI-first) ✅
- Saved accounts file: `accounts.json`
- `wallet_cli.py --list-accounts` prints saved accounts (chain, address, default assets)
- Default assets: `wallet_cli.py --account <name>` uses `default_assets` when `--assets` is not provided
- `wallet_cli.py --save-account <name> --address <pubkey> --chain solana --assets ...` writes/updates `accounts.json`
- Swap entry V0 (redirect):
  - `wallet_cli.py --swap-from sol --swap-to usdc` prints a Jupiter swap URL
  - when `--account` has an address, it prints the wallet address too

### Phase 5 — V1 runway: API + Web UI + Phantom auth primitives ✅
- FastAPI app (`api/`) exposing the engine:
  - `GET /health`, `GET /accounts`
  - `GET /portfolio/latest`, `GET /portfolio/history`
  - `POST /refresh/balances` (Solana read-only, uses `accounts.json`, cooldown + force)
  - `POST /refresh/prices` (CoinGecko + optional Dex fallback, cooldown + force)
- Web UI cockpit served by FastAPI:
  - `GET /ui` with account select + refresh buttons + holdings + history
  - nicer asset labels in UI via `display` field (for example SNP500)
- Portfolio history now “alive”:
  - refresh flows write portfolio snapshots so history grows over time
- Phantom connect + sign message in `/ui`:
  - connect wallet → display pubkey
  - sign message → display signature + message preview
  - disconnect supported

### Phase 6 — Devnet transaction surface + support-mode polish ✅
- Send SOL card added inside `/ui`
- Real browser-side Solana transaction build
- Phantom sign/send integration path
- Send transaction state machine:
  - Draft
  - Awaiting Signature
  - Submitted
  - Confirmed / Failed
- Preflight balance check before opening Phantom:
  - shows exact wallet balance
  - estimated fee
  - total needed
- Live devnet wallet balance display in wallet card
- In-app devnet airdrop helper using Solana RPC `requestAirdrop`
- Better airdrop error translation:
  - clearer messages for 429 / faucet-empty / public devnet unavailability
- Activity Log added to `/ui`
- Duplicate wallet UI issue fixed
- Honest current status:
  - send path works
  - airdrop request path works
  - main blocker is external public devnet funding availability, not app architecture

---

## What is not shipped yet (next up)

### V1.5 — Swap intelligence (Solana-first)
- In-app swap form
- Quote / route data
- Route comparison UI
- Best-choice recommendation
- Clear route explanation
- Honest quote failure states

### V2 — Swap execution handoff
- Chosen route → wallet-signed execution
- Status / confirmation UX for swaps
- No extra wallet-layer markup as a core product principle

### Other near-term items
- Receive UX
- Send SPL tokens
- `/ui` cleanup / refactor away from giant inline HTML
- GitHub / README / docs polish
- Screenshot / demo asset refresh