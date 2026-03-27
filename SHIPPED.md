# Shipped (High-level)

This file is the quick “what exists right now” snapshot.
Updated weekly (and after major milestones).

## Current product snapshot

Web3 Digest currently exists as a **wallet-connected web app** with 2 main layers:

### 1. Connected wallet / portfolio foundation
- connect Phantom
- inspect holdings data and history from the app’s backend
- view portfolio and activity information
- use basic wallet-connected flows inside the UI

### 2. Swap-transparency foundation
- enter a swap pair and amount
- see a live ideal/theoretical no-fee baseline
- request executable quote comparison
- inspect:
  - recommended route
  - alternative route(s)
  - direct-route lens
  - route explanation
  - shortfall vs ideal
  - honest provider limitation notes

The product is no longer best described as “wallet prototype with swap ideas.”
It is now more accurately a **wallet-connected execution-transparency app**.

---

## Current demo flows (work today)

### CLI (legacy / still useful)
1. Insert balances (manual or Solana) → SQLite
2. Insert prices (CoinGecko + optional Dex fallback) → SQLite
3. Print wallet report (CLI)

### Web app (current main surface)
1. Open UI: `GET /ui`
2. Refresh balances: `POST /refresh/balances`
3. Refresh prices: `POST /refresh/prices` (Dex fallback supported)
4. View latest report + history: `GET /portfolio/latest`, `GET /portfolio/history`
5. Connect Phantom / disconnect / sign message
6. Attempt devnet Send SOL with transaction state UI
7. Run preflight balance checks before opening Phantom
8. View live devnet wallet balance
9. Request devnet airdrop from inside the UI (with diagnostics)
10. Use the swap surface to:
   - choose a token pair
   - enter an amount
   - see an ideal/theoretical live baseline
   - preview executable routes
   - compare recommended / alternatives / direct route
   - inspect route explanation and product notes
11. Review recent actions in the Activity Log

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

### Phase 5 — API + Web UI + Phantom connection boundary ✅
- FastAPI app (`api/`) exposing the engine:
  - `GET /health`, `GET /accounts`
  - `GET /portfolio/latest`, `GET /portfolio/history`
  - `POST /refresh/balances` (Solana read-only, uses `accounts.json`, cooldown + force)
  - `POST /refresh/prices` (CoinGecko + optional Dex fallback, cooldown + force)
- Web UI cockpit served by FastAPI:
  - `GET /ui` with account select + refresh buttons + holdings + history
  - nicer asset labels in UI via `display` field
- Portfolio history now grows through refresh flows
- Phantom connect + sign message in `/ui`
- Disconnect supported

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
  - exact wallet balance
  - estimated fee
  - total needed
- Live devnet wallet balance display in wallet card
- In-app devnet airdrop helper using Solana RPC `requestAirdrop`
- Better airdrop error translation:
  - clearer messages for 429 / faucet-empty / public devnet unavailability
- Activity Log added to `/ui`
- Honest status:
  - send path works
  - airdrop request path works
  - devnet funding remains externally unreliable

### Phase 7 — Swap-transparency foundation ✅
- Swap card added inside `/ui`
- Solana-first quote preview surface
- Executable quote comparison built around Jupiter-first route data
- Recommended route block
- Alternative route block
- Direct-route comparison block
- Raw quote debug JSON available for support-mode inspection
- Product-facing recommendation summary now includes:
  - selection basis
  - route availability context
  - “Why this route?”
  - softer note for Jupiter free-tier broader-search limitation
- Cleaner direct-route explanation
- Route shortfall vs ideal wording added

### Phase 8 — Baseline/reference engine split ✅
- Extracted reusable backend helper for theoretical baseline construction
- Added `GET /swap/inline-baseline`
- Separated:
  - ideal/theoretical reference pricing
  - executable quote request flow
- Live baseline updates can now exist independently from executable route preview
- Current design direction is now supported technically:
  - baseline/reference layer
  - execution-intelligence layer

---

## What is meaningfully shipped in product terms

A connected user can now:

- connect Phantom
- inspect wallet-connected data in the app
- see an ideal no-fee reference for a trade
- preview executable swap routes
- compare recommended route vs alternatives
- inspect a direct-route lens separately
- understand why a route was recommended
- see a visible gap between ideal reference and executable outcome

This is the first real version of the product’s core wedge:
**swap transparency on top of a connected wallet experience.**

---

## What is not shipped yet

### Swap-transparency next layer
- fuller cost accounting / estimated total swap cost
- richer venue / provider comparison beyond Jupiter-first
- more advanced route explanation and comparison UX
- final two-panel swap input design

### Connected dashboard next layer
- richer holdings/dashboard experience
- improved token presentation beyond minimal wallet-style numbers
- later charts / asset inspection / stronger connected portfolio UX

### Execution layer
- swap execution handoff through wallet signing
- status / confirmation UX for swaps
- no-extra-wallet-layer-markup principle made more explicit in execution flow

### Other near-term items
- Receive UX
- Send SPL tokens
- `/ui` cleanup / refactor away from giant inline HTML
- GitHub / README / docs polish
- screenshot / demo asset refresh

---

## Current honest status

### Strong now
- wallet-connected architecture
- Phantom connection boundary
- swap-transparency skeleton
- live ideal baseline logic
- executable quote comparison foundation
- clearer product-facing route explanation

### Still early
- comparison is still Jupiter-first
- cost model is still incomplete
- final UI shape is not yet there
- connected dashboard layer is still secondary
- mobile awareness is strategic, not yet fully reflected in the UI

---

## Best one-line description of what exists right now

**Web3 Digest is now a wallet-connected swap-transparency prototype with real route comparison, ideal-reference pricing, and a credible path toward a stronger connected dashboard experience.**