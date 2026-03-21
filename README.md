# Web3 Digest

**Web3 Digest is an execution-intelligence layer for swaps, wrapped in a wallet-like experience.**

It helps users compare swap routes, understand costs, and choose the best execution with no hidden wallet-layer markup.

Project status: **Alpha**

---

## What this project is

Web3 Digest is not trying to be just another wallet UI, just another swap button, or just another portfolio dashboard.

It is a product that aims to help users:

- compare
- understand
- choose
- execute

with clearer cost visibility, more honest route transparency, and a stronger non-custodial signing boundary.

The long-term north star is simple:

**Make swaps feel free: no hidden wallet tax, radically transparent costs, and execution that minimizes total user cost as much as possible.**

---

## Product direction

### Mission
Help people make better swaps by making execution transparent, understandable, and low-cost.

### Vision
Build the most trusted, user-friendly swap experience in crypto — simple enough for non-crypto natives, transparent enough for power users.

### Purpose
Protect users from blind execution, hidden wallet-layer costs, and route opacity.

### Core principles
- **Non-custodial first** — the connected wallet signs; the app compares, explains, and orchestrates.
- **Wallet signs, app explains** — the wallet is the signing boundary, not the swap product.
- **No hidden wallet markup** — we cannot remove all swap costs, but we aim to remove extra wallet-layer tax and make total cost visible.
- **Truthful metrics** — stale, missing, or partial data should be shown honestly.
- **Comparison before execution** — users should understand what they are choosing before they swap.

---

## Why this matters

Many crypto users still swap through wallet UIs that:

- hide route quality
- make total cost hard to understand
- surface token amounts more clearly than economic outcome
- make it hard to compare meaningful alternatives
- feel expensive without clearly explaining why

Web3 Digest exists to make swaps feel understandable instead of mysterious.

---

## Current state

The project has moved beyond a read-only portfolio prototype.

Today it already includes:

- a CLI wallet/reporting foundation
- a FastAPI backend
- a browser UI served by the API
- Phantom connect / disconnect / sign message support
- live devnet wallet balance display
- in-app devnet airdrop helper
- real Send SOL flow on devnet
- real Solana quote preview flow
- human-readable recommendation / protection / route path UX
- support-style quote and transaction diagnostics

---

## What works today

### CLI (V0)
- Insert balances (manual or Solana) into SQLite
- Insert prices (CoinGecko + optional Dex fallback) into SQLite
- Print a wallet report from stored snapshots

### Web UI (V1 / V1.5 runway)
- Open the UI at `GET /ui`
- Refresh balances and prices
- View latest portfolio report and history
- Connect Phantom
- Sign a message
- View live devnet wallet balance
- Request devnet airdrop from inside the UI
- Send SOL on devnet with real transaction confirmation
- Preview swap quotes inside the UI
- Review:
  - recommendation
  - you spend / you receive
  - minimum received
  - protections
  - route path
  - route explanation
  - support-style error states

---

## Swap UX philosophy

The current direction is to make the **economic result** clearer than typical swap UIs.

For each route, the product should prioritize:

1. recommendation / choice framing
2. what the user spends
3. what the user receives
4. estimated total swap cost
5. protections
6. route transparency
7. expandable debug details

### Planned default comparison surface
The comparison surface is being designed around **2 blocks**:

#### 1. Recommended route
A top recommended route chosen by the main ranking logic.

Inside it:
- **Other options**
  - 2nd best
  - 3rd best

These alternatives will be ranked by the **same core metric** as the recommendation, so the product stays transparent and internally consistent.

#### 2. Direct route check
A separate lens for the most direct / fewer-step route.

This block is meant to show a more direct path that may be easier to inspect, even if it is not always the best total-value route.

### Cost philosophy
The key user-facing metric will be:

**Estimated total swap cost**

And the displayed cost breakdown must add up **exactly** to that headline number.

Initial simple breakdown labels:
- **Execution cost**
- **Network fee**
- **Extra wallet fee** (only if it exists)

---

## Architecture at a glance

- **Python**
  - portfolio engine
  - API layer
  - refresh scripts
  - persistence logic
  - ranking / comparison logic

- **SQLite**
  - balances
  - prices
  - portfolio snapshots
  - history-first architecture

- **HTML + JavaScript**
  - browser UI
  - wallet integration
  - swap comparison surface
  - future execution UX

- **Wallet boundary**
  - browser wallet provider
  - user-controlled signing
  - no seed phrase / private key handling by the app

---

## Project structure

Typical important files / areas:

- `api/`
  - FastAPI backend
  - `/ui`
  - refresh endpoints
  - portfolio endpoints
  - swap quote endpoint

- `wallet_cli.py`
  - CLI wallet/report entrypoint

- `db.py`
  - SQLite persistence

- `portfolio.py`
  - portfolio computations and report logic

- `token_registry.py`
  - token metadata / mint normalization / pricing mappings

- `accounts.json`
  - saved account configuration

- docs:
  - `VISION.md`
  - `ROADMAP.md`
  - `SHIPPED.md`
  - `TECHNICAL_DEEP_DIVE.md`

---

## Version ladder

### V0 — Read-only wallet foundation
- balances
- prices
- history
- CLI report
- truthful stale/missing data handling

### V1 — Connected wallet runway
- Phantom connect / sign
- browser wallet cockpit
- Send SOL on devnet
- transaction state UI
- support-style diagnostics

### V1.5 — Swap intelligence surface
- in-app swap form
- quote provider integration
- recommendation / protections / path
- honest quote UX
- support-style quote failures

### V2 — Ranked comparison surface
Planned:
- recommended route
- 2nd best
- 3rd best
- direct route check
- coherent cost ranking
- expandable option details

### V2.5 — Swap execution handoff
Planned:
- choose route
- hand transaction to wallet for signing
- execute from inside the UI
- show status / confirmation / failure clearly

### V3+ — deeper comparison and multichain expansion
Planned:
- stronger ranking logic
- direct venue/provider integrations
- multichain execution-intelligence model
- richer support/debugging layers

---

## Near-term roadmap

### Next major build
Turn the current single-quote swap UI into a **ranked comparison surface** with:

- **Recommended route**
- **Other options**
  - 2nd best
  - 3rd best
- **Direct route check**

### After that
- route selection
- swap execution handoff
- stronger cost model
- direct venue/provider comparison
- receive UX
- send SPL tokens
- UI polish
- docs / GitHub / application packaging

---

## What is not shipped yet

- ranked multi-option comparison surface
- 2nd-best / 3rd-best route cards
- finalized direct-route check block
- actual swap execution
- independent venue/provider comparison
- polished production-grade UI
- final packaging of docs / screenshots / public project story

---

## Safety and testing

- early versions remain **non-custodial**
- transaction flows are tested in safe environments first
- devnet is used for wallet/send testing
- truthful failure is preferred over fake success

Current status remains **Alpha**.

---

## Why this project also matters personally

This project is also intentionally designed to:

- teach real engineering through a hands-on product
- become a strong GitHub showcase
- support wallet / developer support / integration support / product-facing roles in Web3
- grow from a learning project into something with real user value

---

## Long-term product sentence

**Web3 Digest aims to become an execution-intelligence layer for swaps, wrapped in a wallet-like experience — starting on Solana, making execution transparent and low-cost, and helping users compare, understand, and choose the best route without hidden wallet-layer markup.**
