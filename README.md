# Web3 Digest

**Web3 Digest is a wallet-connected execution comparison engine for Solana swaps.**

It helps users connect Phantom, compare real quote paths, understand route tradeoffs, and make better swap decisions with clearer cost, benchmark, and execution visibility.

Project status: **Alpha**

---

## What this project is

Web3 Digest is **not** trying to become a new wallet competing with Phantom.

Instead, it sits **on top of trusted wallets like Phantom** and focuses on a different problem:

- helping users understand what they are about to swap into
- comparing execution outcomes more clearly
- showing the gap between theoretical reference and quoted reality
- making execution feel more transparent and less mysterious
- turning swap decisions into something users can inspect instead of blindly accept

The product direction is simple:

**Connect Phantom. Compare swap execution honestly. Execute selected routes safely through Phantom. Expand the connected dashboard experience after the swap wedge is strong.**

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

- quote comparison
- execution transparency
- theoretical reference vs quoted reality
- direct-route inspection
- route explanation
- route-shape visibility
- support-style diagnostics
- cost visibility where available
- selected swap execution through Phantom for supported providers
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

Build the most trusted, user-friendly **swap execution-intelligence layer** in crypto:

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

The project has moved beyond a read-only portfolio prototype and beyond a single-router quote demo.

Current phase: **Executable Solana swap-intelligence alpha**.

Today it includes:

- CLI wallet/reporting foundation
- FastAPI backend
- browser UI served by the API
- Phantom connect / disconnect / sign message support
- live devnet wallet balance display
- in-app devnet airdrop helper
- real Send SOL flow on devnet
- Solana swap quote preview surface
- multi-universe quote comparison engine
- Recommended / Direct / Alternatives route structure
- guarded execution through Phantom for supported providers
- prepared-transaction preflight diagnostics before Phantom opens
- live reference baseline updates while typing
- recommended-route cost summary in USD
- estimated network fee display where available
- explicit route-fee display when available
- user-facing route explanation and support-style diagnostics
- fail-soft behavior for unsupported quote universes

---

## Current quote universes

The current Alpha can compare real successful quotes across several recognizable swap/execution surfaces.

### Jupiter

Quote + executable through Phantom where supported.

### Raydium

Quote + executable through Phantom where supported.

### Orca

Explicit pool candidate model. Quote + executable through Phantom where supported.

Native SOL input is supported through Orca's ATA wrapping strategy. The app preflights prepared transactions and blocks before Phantom when setup/rent/fee SOL is insufficient.

### Meteora

DLMM-only curated quote path. Comparison-only and non-clickable for now.

### Phantom

Wallet-routing quote research surface. Comparison-only and curated for supported SOL-to-SPL pairs.

### PumpSwap

Quote + executable for direct SOL <-> pump-token paths where a real canonical PumpSwap pool is discovered.

Composed paths such as pump-token -> SOL -> USDC are not implemented yet.

---

## Current token coverage

Current curated swap testing routes include:

- SOL → USDC
- SOL → BONK
- SOL → WIF
- SOL → POPCAT
- SOL → CHAD
- SOL → SPX6900
- SOL → FIGURE
- pasted Solana mints with safely resolved decimals, including SNP500:
  `3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump`

The current rule is simple:

**No fake quotes.**

Only real successful quotes render as visible route cards. Unsupported venues fail softly and stay in diagnostics/debug output.

---

## What works today

### CLI foundation

- insert balances into SQLite
- insert prices into SQLite
- print a wallet report from stored snapshots

### Web app

- open the UI at `GET /ui`
- refresh balances and prices
- view latest portfolio report and history
- connect Phantom
- sign a message
- view live devnet wallet balance
- request devnet airdrop from inside the UI
- send SOL on devnet with transaction state handling
- preview swap quotes inside the UI
- prepare, preflight, sign in Phantom, and submit supported swap routes
- review:
  - theoretical reference baseline
  - recommended route
  - direct-route lens
  - alternatives
  - minimum received where available
  - route path
  - route shape / step count
  - route explanation
  - execution gap vs reference
  - estimated route cost story
  - explicit route fees when available
  - estimated network fee where available
  - support-style error states and notes

### Live execution checkpoints

The Alpha has executed real Solana mainnet swaps through Phantom for:

- Jupiter
- Raydium
- Orca
- PumpSwap

Phantom remains the signer/custody layer. Web3 Digest prepares, preflights, and submits only after the user approves in Phantom.

Recent verified paths include:

- Orca SOL -> USDC after fixing native SOL wrapping
- USDC -> SNP500 through Jupiter using temporary external-token metadata
- SNP500 -> SOL through PumpSwap direct SOL <-> pump-token routing

---

## Swap UX philosophy

The product should make the **economic result** easier to understand than typical swap UIs do.

### Core rule

The product must clearly separate:

- **theoretical reference**
- **real quoted/executable output**
- **known explicit costs**

Those are different layers and should stay separate in both UX and architecture.

### Current comparison surface

The swap surface is built around:

#### 1. Live reference layer

- choose tokens
- type amount
- see live theoretical conversion

#### 2. Execution-intelligence layer

- Preview Quote
- Recommended route
- Direct route check
- Alternatives
- route explanation
- execution gap vs reference
- separate fee/cost visibility where available

### Why this matters

A key product insight is that:

- router-reported `priceImpactPct`
- the **gap vs theoretical reference**
- known explicit route costs

are not the same metric.

They should not be collapsed into one vague “fee” number.

---

## Current implementation notes

The current swap surface is useful, but it is still Alpha.

### Honest notes about the current build

- swap comparison is still the primary product surface
- Jupiter, Raydium, Orca, and PumpSwap have guarded execution paths where supported
- Meteora and Phantom remain quote/comparison-only
- route fees are shown separately when explicitly available in the quote
- estimated network fee is shown separately from the benchmark comparison
- network-fee estimation still needs hardening before production-grade execution
- token coverage combines curated tokens with temporary recognized pasted mints
- external-token reference/valuation can be misleading when cached, stale, or unverified
- the UI structure is improving but is not final visual polish

That means the product wedge is real, but parts of the implementation still need hardening.

---

## Product design direction

The current inline reference row is a **transitional UI**.

The longer-term swap input should evolve toward a more stacked, two-panel, wallet-connected experience where:

- the user types directly in the source token panel
- the destination panel shows the theoretical converted amount live
- executable route comparison stays below that as a separate action and intelligence layer

Current work is focused first on:

- engine
- behavior
- product logic
- cost honesty
- interaction clarity
- clear separation of concerns

Pretty UI and final polish come later.

---

## Interaction direction

The current swap surface is being shaped so that it can later become actionable cleanly.

### Current interaction rules

- Recommended is the main card
- Direct is the simpler comparison lens
- Alternatives are distinct quote/comparison universes
- quote-only routes are non-clickable
- expand and execute should remain separate behaviors
- future primary actions should be **buttons**, not whole-card taps

### Current actionability rule

Routes are clickable only when the provider has a real prepare + submit path, the quote variant is supported, and route readiness says it is execution-ready.

Executable providers today:

- Jupiter
- Raydium
- Orca
- PumpSwap direct SOL <-> pump-token paths

Meteora and Phantom remain comparison-only.

This keeps the surface mobile-safer and easier to understand.

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

The current comparison surface started Jupiter-first, but it now has a real multi-universe direction.

The roadmap is expected to expand into more honest quote and execution surfaces so route comparison becomes:

- richer
- more credible
- more transparent
- more aligned with the execution-intelligence promise

Near-term order:

1. keep validating live execution paths with small swaps
2. polish stale-balance and external-token valuation UX
3. test more pasted mints and suspicious/scam-token warnings
4. improve token search/discovery
5. evaluate future composed routes and Meteora execution separately

---

## Platform direction

### Web first

The product is being built as a **web app first** because that is the right path for:

- fast iteration
- clean demos
- GitHub showcase
- early product validation

### Mobile-aware

Even though native mobile is not the first build, the long-term direction should stay **mobile-aware**.

That matters because much real-world swapping behavior — especially in fast-moving meme/token environments — is heavily phone-first, and Phantom’s strongest real-world advantage is its mobile usage habit and polished UX.

So the right path is:

- web first
- mobile-aware interaction patterns now
- responsive/mobile refinement later
- native mobile only if the product earns it

---

## Architecture at a glance

- **Python**
  - portfolio engine
  - API layer
  - refresh scripts
  - persistence logic
  - swap ranking / comparison logic
  - quote universe integrations
  - provider prepare/preflight/submit plumbing

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
  - frontend interaction logic

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

- `test_sanity.py`
  - sanity tests for core behavior, registry behavior, and quote fail-soft rules

- `AGENTS.md`
  - repository guidelines for coding agents

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

### V1.5 — execution intelligence engine alpha

- in-app swap form
- live theoretical reference
- multi-universe quote engine
- Recommended / Direct / Alternatives
- benchmark/reference comparison
- route-card cost framing
- honest quote UX
- fail-soft unsupported venues
- curated meme-token coverage

### V2 — guarded swap execution alpha

- Jupiter execution through Phantom
- Raydium execution through Phantom
- Orca execution through Phantom
- PumpSwap execution for direct SOL <-> pump-token paths
- backend prepare/preflight/submit flow
- Phantom remains the signing boundary
- transaction result handling and explorer links

### V2.5 — scalable token intake alpha

- paste token mint
- resolve token metadata
- resolve decimals safely through Solana RPC mint account
- quote temporary recognized external tokens without mutating `TOKEN_META`
- session/localStorage recognized-token UX
- later token search and stronger discovery

### V3 — broader execution intelligence

Planned:

- direct venue/provider execution paths where honest
- richer route/risk intelligence
- stronger cost model
- improved connected dashboard
- mobile-aware product UI
- later multichain expansion if justified

---

## What is not shipped yet

- executable Meteora routes
- Phantom execution/handoff route
- full route-fee decomposition for every quote universe
- final-grade transaction-specific network-fee estimation
- token search / discovery
- composed routes such as PumpSwap token -> SOL -> USDC
- final suspicious/scam mint warning UX
- final two-panel swap input design
- production-grade swap infra hardening
- production-grade polished UI
- richer connected holdings/dashboard experience
- final public packaging of docs / screenshots / demo story

---

## Safety and testing

- early versions remain **non-custodial**
- transaction flows are tested in safe environments first
- devnet is used for wallet/send testing
- truthful failure is preferred over fake success
- unsupported quote universes should fail softly
- visible route cards should come only from real successful quotes

Current status remains **Alpha**.

---

## Why this project matters personally

This project is intentionally designed to:

- teach real engineering through a hands-on product
- become a strong GitHub showcase
- support wallet / developer support / integration support / product-facing roles in Web3
- grow from a learning project into something with real user value

---

## One-line product sentence

**Web3 Digest is a wallet-connected execution comparison engine that helps users compare swap routes, understand tradeoffs, and make better swap decisions on top of trusted wallets like Phantom.**
