# Roadmap — Web3 Digest

This file is the active “where we’re going next” plan for Web3 Digest.

It should stay clean enough to use as the main resume/start point at the beginning of each session.

Updated checkpoint: after guarded execution paths for Jupiter, Raydium, Orca, and PumpSwap, plus recognized external-token swaps.

Latest implementation checkpoints reflected here:

- `0f3f15a` — Fix Orca native SOL wrapping
- `343a2ba` — Support recognized external token swaps

---

## Current phase

**Execution Intelligence Alpha**

Web3 Digest is no longer being treated as “a wallet that can also do swaps.”

It is now clearly a:

**executable Solana swap-intelligence alpha.**

That means:

- Phantom remains the wallet, signer, and security layer
- Web3 Digest becomes the place where users:
  - connect wallet
  - preview a swap
  - compare recognizable execution universes
  - understand benchmark/reference gap
  - understand known route costs where available
  - choose better execution paths
  - execute supported routes through Phantom

The product wedge is:

**connect Phantom, compare swap outcomes honestly, explain costs clearly, then execute supported routes safely.**

---

## Product identity

**Web3 Digest is an execution-intelligence layer for swaps, wrapped in a wallet-connected experience.**

### Mission

Help people make better swaps by making execution transparent, understandable, and low-cost.

### Vision

Build the most trusted, user-friendly swap experience in crypto — simple enough for non-crypto natives, transparent enough for power users.

### Purpose

Protect users from blind execution, hidden wallet-layer costs, and route opacity.

### Direction

Compare multiple execution universes, execute supported routes through Phantom, expand scalable token intake, improve cost modeling, and later evaluate broader venue/multichain execution intelligence.

### Moat

We make execution understandable, trustworthy, and cost-transparent — and we let users compare meaningful alternatives instead of executing blindly.

### North star

**Make swaps feel free:** no hidden wallet tax, radically transparent costs, and execution that minimizes total user cost as much as possible.

### One-line pitch

**Web3 Digest helps users compare swap routes, understand costs, and choose the best execution with no hidden wallet-layer markup.**

---

## Current shipped local state

The current local build has moved beyond the original Jupiter-only prototype and beyond quote-only swap comparison.

### Core app foundation

- FastAPI backend
- browser UI at `/ui`
- Phantom connect/signing foundation
- swap quote + guarded execution surface
- inline benchmark/reference baseline
- Recommended / Direct / Alternatives route structure
- route cards with user-facing “Via X” labeling
- quote-only vs clickable behavior fields
- backend prepare/preflight/submit flow for supported providers
- transaction diagnostics for setup/rent/wSOL failures
- fail-soft diagnostics for unsupported venues
- tests covering registry, quote, prepare, preflight, execution gating, and external-token behavior

### Current quote universes

The quote engine now compares multiple recognizable execution universes.

#### Jupiter

- quote + executable through Phantom
- used for primary reference/recommendation behavior where it wins
- USDC -> SOL preflight passed and opened Phantom during reverse-route testing

#### Raydium

- real quote path
- executable through Phantom where supported
- live SOL -> BONK and SOL -> USDC swaps succeeded on Solana mainnet

#### Orca

- explicit pool candidate model
- only shows real successful quotes
- unsupported pairs fail softly
- executable through Phantom where supported
- native SOL wrapping fixed by using `setNativeMintWrappingStrategy("ata")`
- SOL -> USDC executed successfully on Solana mainnet
- high/MAX SOL amounts block before Phantom when setup/rent/fee shortfall exists

#### Meteora

- DLMM-only curated quote path
- comparison-only
- non-clickable for now
- no fake DLMM candidates

#### Phantom

- wallet-routing quote research surface
- comparison-only
- non-clickable
- curated SOL-to-SPL allowlist only

#### PumpSwap

- direct SOL <-> pump-token quote + execution where a canonical pool is discovered
- PumpSwap direct coverage is not a composed route engine yet
- SNP500 -> SOL executed successfully on Solana mainnet

---

## Current token coverage

### SOL → USDC

Broad support across major venues.

### SOL → BONK

Supported across several quote universes, including Jupiter, Raydium, Orca, Meteora, and Phantom where available.

### SOL → WIF

Supported across Jupiter, Raydium, Orca, and Phantom where available. Meteora/PumpSwap remain fail-soft unless real support exists.

### SOL → POPCAT

Added as a curated Solana meme token.

### SOL → CHAD

Added as a curated Solana meme token.

### SOL → SPX6900

Added as a curated Solana meme token.

### SOL → FIGURE

PumpSwap-only curated test token used to validate Pump.fun-style quoting.

### Pasted external Solana mints

Pasted mint recognition is live for Alpha testing.

Recent validated mint:

- SNP500: `3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump`

The app can resolve metadata/decimals without mutating `TOKEN_META`, store temporary recognized tokens in the browser session/localStorage, refresh recognized-token balances, and quote recognized external tokens after decimals are known.

---

## Locked product rules

These rules should remain stable unless intentionally changed.

### No fake quotes

Only real successful quotes should render as route cards.

Unsupported venues should appear only as diagnostics/debug information.

### No fake execution

A route card should only have an execution CTA if the app can actually execute that path honestly.

### Quote-only means quote-only

Meteora and Phantom remain non-clickable unless a real execution path is implemented.

Jupiter, Raydium, Orca, and PumpSwap are clickable only through guarded readiness/capability/variant checks.

### Ranking remains honest

Ranking is based on actual quoted receive amount.

Do not manipulate ranking to make a venue look better.

### Curated means curated

Curated pool/venue support should not be generalized unless the backend can support it honestly.

### Solana first

The current wedge is Solana swap execution transparency.

Multichain expansion comes later only after the Solana wedge is strong.

---

## Current product assessment

The engine now reflects the product mission.

It can show that a swap is not one invisible black-box price. It can compare multiple execution universes, show which ones succeed, show which ones fail, and avoid pretending that unsupported venues work.

Current status:

| Area | Status |
|---|---|
| Multi-universe quote engine | Strong alpha |
| Token coverage | Small but useful curated set |
| Cost transparency | Present but needs clearer UX wording |
| Recommendation display | Working but needs real-world review |
| Execution | Working alpha for Jupiter, Raydium, Orca, PumpSwap direct |
| Final UI | Not ready yet |
| Public beta | Not ready yet |

Current conclusion:

**The product thesis is proven. The next work is live testing, clarity, external-token safety, route expansion, and production hardening.**

---

## Macro roadmap

## Phase 1 — Comparison Engine Stabilization + Decision UX

### Goal

Make the current comparison surface clearly reflect the mission.

The next sessions should focus on running the app, testing real routes, and improving what is already there.

### Work

- start the server
- test supported pairs:
  - SOL → USDC
  - SOL → BONK
  - SOL → WIF
  - SOL → POPCAT
  - SOL → CHAD
  - SOL → SPX6900
  - SOL → FIGURE
- inspect quote cards
- verify which venues quote successfully
- verify unsupported venues fail softly
- improve obvious confusing wording
- improve card labels and route status
- improve cost explanation where needed
- keep diagnostics useful but not noisy
- make quote-only vs executable status clear

### Product questions to answer

For each route, can the user understand:

- what route gives the most?
- what route is simpler/direct?
- what venue produced the quote?
- what is the receive amount?
- what is the estimated cost versus reference?
- what is quote-only?
- what can actually be executed?
- why did unsupported venues fail?

### Success criteria

- the current cards feel aligned with the mission
- costs and route labels are understandable
- unsupported routes do not confuse the user
- no fake route cards appear
- the engine feels stable enough to build execution on top

---

## Phase 2 — Guarded Execution Through Phantom

### Goal

Keep the shipped execution paths honest, safe, and debuggable.

This is the phase where Web3 Digest has already become more than an analysis tool.

### Scope

- Jupiter, Raydium, Orca, and PumpSwap direct paths are executable where supported
- Meteora and Phantom remain comparison-only
- Phantom remains the signing boundary
- user approves in wallet
- app sends/broadcasts the transaction
- app preflights before Phantom and shows confirmation or translated error

### Work

- keep live-testing small swaps
- harden prepared-transaction preflight diagnostics
- keep SOL setup/rent/fee checks conservative and explainable
- improve stale-balance / post-swap refresh UX
- preserve user approval in Phantom
- show transaction result and explorer links clearly
- keep Meteora/Phantom non-clickable until real execution paths exist

### Product rule

Do not make a route executable unless prepare, preflight, Phantom signing, and backend submit are all real for that provider/variant.

---

## Phase 3 — Scalable Token Intake

### Goal

Stop relying on manual token additions.

Manual token additions are useful for a small curated demo set, but they do not scale. New meme tokens appear constantly, and the project should not become data-entry work.

### Step 3A — Paste mint

Status: **shipped as Alpha**.

Let the user paste a Solana token mint.

The app should try to resolve:

- token symbol
- token name
- decimals
- price/reference data if available
- Jupiter quote/execution where supported
- Raydium quote/execution where supported
- Orca quote/execution where supported
- PumpSwap direct SOL <-> pump-token quote/execution where supported
- Phantom quote benchmark where supported
- other venues only when honest support exists

Important shipped behavior:

- decimals are resolved through Solana RPC mint account data
- `/tokens/resolve` exposes `can_quote`
- temporary recognized tokens live in browser session/localStorage
- `TOKEN_META` is not mutated automatically
- recognized external-token balances are included in refresh requests
- PumpSwap remains direct SOL <-> pump-token only, not a composed-route engine

### Step 3B — Token search

Let the user search by symbol/name and resolve a mint from a reliable source.

Examples:

- POPCAT
- FARTCOIN
- MEW
- GIGA
- PNUT
- BOME

### Step 3C — Token discovery

Later, add discovery from external token/liquidity sources.

Possible future sources:

- DexScreener
- Jupiter token lists
- Raydium pools
- Pump.fun / PumpSwap-related sources
- other Solana liquidity/trending sources

### Product rule

Do not manually add hundreds of tokens.

Build a system that can resolve and test tokens dynamically.

---

## Phase 4 — Expand Executable Universes

### Goal

Avoid becoming only a Jupiter execution wrapper.

After the current executable paths stabilize, evaluate and gradually add additional execution paths only where technically honest and worth it.

### Possible order

1. Meteora DLMM execution path
2. composed PumpSwap token -> SOL -> USDC style routes
3. broader external-token route discovery
4. Phantom comparison/handoff path if measurable and honest
5. additional Solana venues only when prepare/preflight/submit are real

### Product rule

Execution expansion should be careful.

Do not make a universe clickable until the app can really execute or hand off that exact path.

---

## Phase 5 — Product UI + Private Alpha

### Goal

Make Web3 Digest usable by someone who is not us.

This is where the product should become cleaner, mobile-aware, and ready for small external testing.

### Work

- redesign route-choice surface around the real product model
- improve mobile-friendly swap layout
- improve visual hierarchy
- add clearer warnings/disclaimers
- add clearer quote freshness and source labels
- hide raw diagnostics by default
- keep inspect/debug mode available
- improve setup/docs
- prepare a small demo/testing path

### Private alpha ready when

- comparison surface is understandable
- Jupiter/Raydium/Orca/PumpSwap execution paths remain stable in small live tests
- quote-only routes are clearly labeled
- token intake has paste-by-mint support and clear unresolved-decimals behavior
- error handling is reasonable
- another person can test it without needing constant explanation

---

## Phase 6 — Public Beta / Broader Intelligence Layer

### Goal

Move from project to product.

### Future work

- broader token discovery
- more quote universes
- more executable universes
- better route/risk intelligence
- stronger cost modeling
- analytics/logging
- hosted demo
- mobile-first product experience
- possible multichain expansion

---

## Cost model direction

The cost model should keep two ideas separate.

### Benchmark comparison layer

This answers:

**How does this real quote compare to the theoretical/reference value?**

It should show:

- you pay
- ideal/reference output
- real vs ideal gap

This is a transparency layer, not a literal fee layer.

### Route-card explicit cost layer

This answers:

**What known route-level costs are visible for this swap?**

It may show:

- network cost
- disclosed route fees
- platform/app fee if applicable
- unavailable/not disclosed states

### Product rule

Do not invent precision.

If a cost is not known, say it is unavailable or not disclosed.

---

## Route-card structure

The route-choice structure remains:

- Recommended
- Direct
- Alternatives

### Recommended

Best current executable route, or best quote clearly marked if non-executable.

Executable recommendations can come from any currently supported executable provider: Jupiter, Raydium, Orca, or PumpSwap direct SOL <-> pump-token paths.

### Direct

Simplest meaningful route lens.

Direct is not automatically second-best. It is the simpler/easier-to-inspect option.

### Alternatives

Distinct comparison universes, not duplicate internal route noise.

Examples:

- Via Raydium
- Via Orca
- Via Meteora
- Via Phantom
- Via PumpSwap

---

## UI wording direction

Default visible card wording should prioritize user-facing execution surfaces:

- Via Jupiter
- Via Raydium
- Via Orca
- Via Meteora
- Via Phantom
- Via PumpSwap

Internal route/provider names should move into expanded details or inspect mode.

Examples:

- BisonFi
- HumidiFi
- Scorch
- Quantum
- pool addresses
- bin arrays
- route steps

---

## What is deprioritized for now

The connected dashboard, holdings display, and wallet-cockpit layer are useful, but they are not the lead wedge right now.

They should only be worked on when they support:

- trust
- execution
- post-swap understanding
- support/debugging
- connected identity quality

The lead priority remains:

**swap execution transparency first.**

---

## Next immediate sessions

### Session 1 — external-token polish and safety

Fix or test:

- duplicate SNP500 in the asset list
- 50% / MAX still showing stale-refresh copy after a fresh recognized-token balance
- external-token reference/valuation warnings when price source is cached, stale, or unverified
- random DexScreener mint testing
- suspicious/scam mint warning behavior

Goal:

**make pasted-mint swaps feel safe and understandable without pretending long-tail prices are fully trusted.**

---

### Session 2 — live execution regression pass

Small-amount checks only:

- Jupiter
- Raydium
- Orca
- PumpSwap direct SOL <-> pump-token
- reverse SOL routes where safe

Goal:

**confirm prepare/preflight/Phantom/submit still behave after the external-token work.**

---

### Session 3 — route and provider expansion planning

Evaluate:

- Meteora execution feasibility
- composed routes such as PumpSwap token -> SOL -> USDC
- token search/discovery architecture
- Bubblemaps / holder concentration tiny UX live testing

Goal:

**choose the next provider/product chunk without weakening the safety model.**

---

## Next major milestone

**Executable Swap Intelligence Alpha**

A credible local alpha where a user can:

1. connect Phantom
2. choose a swap pair and amount
3. see a reference/benchmark comparison
4. compare real quote universes
5. understand which route is recommended and why
6. understand known costs and unknowns
7. execute supported Jupiter/Raydium/Orca/PumpSwap routes through Phantom
8. trust that unsupported routes are not being faked

---

## Resume point

Start next session from:

**external-token polish and live-regression checks.**

First action:

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --log-level debug
```

Future dashboard / activity layer:
Evaluate Helius parsed transfer history for wallet activity feed and support-mode diagnostics, after the swap wedge is stable.
