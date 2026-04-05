# Web3 Digest

**Web3 Digest is a wallet-connected execution-transparency app for swaps.**

It helps users connect Phantom, compare routes, understand tradeoffs, and make better execution decisions with clearer cost, route, and execution visibility.

Project status: **Alpha**

---

## What this project is

Web3 Digest is **not** trying to become a new wallet competing with Phantom.

Instead, it sits **on top of trusted wallets like Phantom** and focuses on a different problem:

- helping users understand what they are about to swap into
- comparing routes more clearly
- showing the gap between ideal reference and executable reality
- making execution feel more transparent and less mysterious
- turning swap decisions into something users can inspect instead of blindly accept

The product direction is simple:

**Connect Phantom. Swap with transparency. Expand the connected dashboard experience later.**

---

## Product identity

### Phantom remains the wallet
Phantom handles:

- wallet creation
- custody and key security
- transaction signing
- trusted wallet UX

### Web3 Digest becomes the intelligence layer
Web3 Digest handles:

- route comparison
- execution transparency
- ideal vs executable reference
- direct-route inspection
- route explanation
- route-shape visibility
- support-style diagnostics
- later, a stronger connected holdings/dashboard experience

This is a product built **with Phantom in mind, not against it**.

---

## Mission

Help users make better swaps by making execution:

- transparent
- understandable
- trustworthy
- as low-friction and low-cost as possible

---

## Vision

Build the most trusted, user-friendly **swap transparency layer** in crypto:

- simple enough for non-crypto-native users
- transparent enough for power users
- practical enough to sit on top of wallets people already use

---

## Why this matters

Many swap experiences still make users execute too blindly.

Typical wallet or swap UIs often:

- hide route quality
- compress cost details too much
- make it hard to compare meaningful alternatives
- show token amounts more clearly than economic outcome
- feel expensive without clearly explaining why

Web3 Digest exists to make swaps feel **understandable instead of opaque**.

---

## Current state

The project has moved well beyond a read-only portfolio prototype.

Today it already includes:

- CLI wallet/reporting foundation
- FastAPI backend
- browser UI served by the API
- Phantom connect / disconnect / sign message support
- live devnet wallet balance display
- in-app devnet airdrop helper
- real Send SOL flow on devnet
- swap quote preview surface
- recommended / alternatives / direct-route comparison logic
- live reference baseline updates while typing
- estimated network fee display for swap options
- explicit route fee display when available
- user-facing route explanation and support-style diagnostics

---

## What works today

### CLI foundation
- Insert balances (manual or Solana) into SQLite
- Insert prices (CoinGecko + optional Dex fallback) into SQLite
- Print a wallet report from stored snapshots

### Web app
- Open the UI at `GET /ui`
- Refresh balances and prices
- View latest portfolio report and history
- Connect Phantom
- Sign a message
- View live devnet wallet balance
- Request devnet airdrop from inside the UI
- Send SOL on devnet with transaction state handling
- Preview swap quotes inside the UI
- Review:
  - theoretical reference baseline
  - recommended route
  - alternative route(s)
  - direct-route lens
  - minimum received
  - route path
  - route shape / step count
  - route explanation
  - execution gap vs reference
  - explicit route fees when available
  - estimated network fee
  - support-style error states and notes

---

## Swap UX philosophy

The product should make the **economic result** easier to understand than typical swap UIs do.

### Core rule
The product must clearly separate:

- **theoretical reference**
- **real executable quote**

Those are different layers and should stay separate in both UX and architecture.

### Current comparison surface
The swap surface is built around:

#### 1. Live reference layer
- choose tokens
- type amount
- see live theoretical conversion

#### 2. Execution-intelligence layer
- Preview Quote
- recommended route
- alternatives
- direct-route check
- route explanation
- execution gap vs reference
- separate fee visibility

### Why this matters
A key product insight is that:

- router-reported `priceImpactPct`
- and the **gap vs theoretical reference**

are **not the same metric**.

Both matter, and both should stay visible.

---

## Current implementation notes

The current swap surface is already useful, but it is still Alpha.

### Honest notes about the current build
- swap comparison is currently **Jupiter-first**
- the swap card is currently **quote preview only**, not full swap execution
- route fees are shown separately **when explicitly available in the quote**
- estimated network fee is shown separately from the headline execution-gap framing
- the current swap network-fee estimation path uses a **mainnet RPC call**
- the current frontend still contains a **hardcoded Helius mainnet RPC URL** for that fee-estimation step, which should be moved into safer backend/env-managed config soon

That means the product wedge is real, but parts of the implementation still need hardening.

---

## Product design direction

The current inline reference row is a **transitional UI**.

The longer-term swap input should evolve toward a more stacked, two-panel, wallet-connected experience where:

- the user types directly in the source token panel
- the destination panel shows the theoretical converted amount live
- executable route comparison stays below that as a separate action and intelligence layer

So the current work is focused first on:

- engine
- behavior
- product logic
- cost honesty
- clear separation of concerns

Pretty UI and final polish come later.

---

## Connected dashboard direction

The product may later expand into a stronger wallet-connected dashboard experience, such as:

- better holdings view
- improved token presentation
- clearer asset inspection
- charts / richer portfolio visibility
- better connected portfolio UX than a minimal wallet-number view

But this remains **secondary** to the main wedge.

### Primary wedge
**Swap transparency first. Dashboard expansion second.**

---

## Routing direction

The current comparison surface is **Jupiter-first**, which is the right first step.

But the long-term product should not stop at one provider worldview.

The roadmap is expected to expand into at least **two additional routing/liquidity universes/providers** so route comparison becomes:

- richer
- more credible
- more honest
- more aligned with the transparency promise

---

## Platform direction

### Web first
The product is being built as a **web app first** because that is the right path for:

- fast iteration
- clean demos
- GitHub showcase
- early product validation

### Mobile-aware
Even though native mobile is not the first build, the long-term direction must stay **mobile-aware**.

That matters because much real-world swapping behavior — especially in fast-moving meme/token environments — is heavily **phone-first**, and Phantom’s strongest real-world advantage is its mobile usage habit and polished UX.

So the right path is:

- web first
- responsive and mobile-aware later
- native mobile only if the product earns it

---

## Architecture at a glance

- **Python**
  - portfolio engine
  - API layer
  - refresh scripts
  - persistence logic
  - swap ranking / comparison logic
  - Jupiter quote + instruction plumbing

- **SQLite**
  - balances
  - prices
  - portfolio snapshots
  - history-first architecture

- **HTML + JavaScript**
  - browser UI
  - wallet integration
  - swap comparison surface
  - live reference behavior
  - client-side fee-estimation flow

- **Wallet boundary**
  - browser wallet provider
  - user-controlled signing
  - no seed phrase / private key handling by the app

---

## Project structure

Important areas include:

- `api/`
  - FastAPI backend
  - `/ui`
  - refresh endpoints
  - portfolio endpoints
  - swap quote, instruction, and inline-baseline endpoints

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

### V0 — read-only wallet foundation
- balances
- prices
- history
- CLI report
- truthful stale/missing data handling

### V1 — wallet-connected runway
- Phantom connect / sign
- browser wallet cockpit
- Send SOL on devnet
- transaction state UI
- support-style diagnostics

### V1.5 — swap-transparency foundation
- in-app swap form
- live theoretical reference
- quote provider integration
- recommendation / alternatives / direct-route check
- “Why this route?” explanation
- estimated network fee visibility
- explicit route-fee visibility when available
- honest quote UX and support-style failures

### V2 — stronger comparison surface
Planned:
- richer multi-option comparison
- better route ranking clarity
- clearer cost framing
- more polished swap input UX
- safer config handling for swap infrastructure
- more trustworthy comparison flow

### V2.5 — swap execution handoff
Planned:
- choose route
- hand transaction to wallet for signing
- execute from inside the UI
- show status / confirmation / failure clearly

### V3+ — deeper route intelligence + connected dashboard expansion
Planned:
- direct venue/provider comparison
- multi-provider routing worldview
- stronger holdings/dashboard UX
- richer support/debugging layers
- later multichain expansion if justified

---

## What is not shipped yet

- full swap execution flow from the swap card
- complete cost accounting for swap comparison
- non-Jupiter routing universes/providers
- final two-panel swap input design
- production-grade config cleanup for swap infra
- production-grade polished UI
- richer connected holdings/dashboard experience
- final public packaging of docs / screenshots / demo story

---

## Safety and testing

- early versions remain **non-custodial**
- transaction flows are tested in safe environments first
- devnet is used for wallet/send testing
- truthful failure is preferred over fake success

Current status remains **Alpha**.

---

## Why this project matters personally

This project is also intentionally designed to:

- teach real engineering through a hands-on product
- become a strong GitHub showcase
- support wallet / developer support / integration support / product-facing roles in Web3
- grow from a learning project into something with real user value

---

## One-line product sentence

**Web3 Digest is a wallet-connected execution-transparency app that helps users compare routes, understand tradeoffs, and make better swap decisions on top of trusted wallets like Phantom.**