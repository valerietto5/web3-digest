# Roadmap — Web3 Digest

This file is the active “where we’re going next” plan for Web3 Digest.

It should stay clean enough to use as the main resume/start point at the beginning of each session.

Updated checkpoint: after reaching the first multi-universe swap quote engine.

---

## Current phase

**Execution Intelligence Engine Alpha**

Web3 Digest is no longer being treated as “a wallet that can also do swaps.”

It is now clearly a:

**wallet-connected execution comparison engine for Solana swaps.**

That means:

- Phantom remains the wallet, signer, and security layer
- Web3 Digest becomes the place where users:
  - connect wallet
  - preview a swap
  - compare recognizable execution universes
  - understand benchmark/reference gap
  - understand known route costs where available
  - choose better execution paths
  - later execute selected routes through Phantom

The product wedge is:

**connect Phantom, compare swap outcomes honestly, explain costs clearly, then execute safely.**

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

Compare multiple execution universes first, then expand into execution, scalable token intake, broader venue support, stronger cost modeling, and later multichain execution intelligence.

### Moat

We make execution understandable, trustworthy, and cost-transparent — and we let users compare meaningful alternatives instead of executing blindly.

### North star

**Make swaps feel free:** no hidden wallet tax, radically transparent costs, and execution that minimizes total user cost as much as possible.

### One-line pitch

**Web3 Digest helps users compare swap routes, understand costs, and choose the best execution with no hidden wallet-layer markup.**

---

## Current shipped local state

The current local build has moved beyond the original Jupiter-only prototype.

### Core app foundation

- FastAPI backend
- browser UI at `/ui`
- Phantom connect/signing foundation
- swap quote surface
- inline benchmark/reference baseline
- Recommended / Direct / Alternatives route structure
- route cards with user-facing “Via X” labeling
- quote-only vs clickable behavior fields
- fail-soft diagnostics for unsupported venues
- tests covering major registry and quote behavior

### Current quote universes

The quote engine now compares multiple recognizable execution universes.

#### Jupiter

- primary quote universe
- currently the main executable-capable path
- used for primary reference/recommendation behavior
- future first execution target

#### Raydium

- real quote path
- comparison-only
- non-clickable for now
- no fake execution CTA

#### Orca

- explicit pool candidate model
- only shows real successful quotes
- unsupported pairs fail softly
- no fake quote cards

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

- curated-only
- currently used only for the FIGURE docs/test token path
- not treated as a generic Pump.fun token solution yet

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

---

## Locked product rules

These rules should remain stable unless intentionally changed.

### No fake quotes

Only real successful quotes should render as route cards.

Unsupported venues should appear only as diagnostics/debug information.

### No fake execution

A route card should only have an execution CTA if the app can actually execute that path honestly.

### Quote-only means quote-only

Raydium, Orca, Meteora, Phantom, and PumpSwap remain non-clickable unless a real execution path is implemented.

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
| Execution | Not live yet |
| Final UI | Not ready yet |
| Public beta | Not ready yet |

Current conclusion:

**The product thesis is proven. The next work is stabilization, clarity, execution, and scalability.**

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

## Phase 2 — Jupiter Execution Through Phantom

### Goal

Make the recommended Jupiter route executable through Phantom.

This is the step where Web3 Digest becomes more than an analysis tool.

### Scope

- Jupiter execution first
- keep all other universes quote-only
- Phantom remains the signing boundary
- user approves in wallet
- app sends/broadcasts the transaction
- app shows confirmation or translated error

### Work

- connect selected Jupiter quote to swap transaction build path
- create pre-execution confirmation state
- build/sign/send through Phantom
- preserve user approval in wallet
- add preflight checks
- add error translation
- show transaction result
- keep Raydium/Orca/Meteora/Phantom/PumpSwap non-clickable until real execution paths exist

### Product rule

Only Jupiter gets execution first.

Do not make every quote card executable at once.

---

## Phase 3 — Scalable Token Intake

### Goal

Stop relying on manual token additions.

Manual token additions are useful for a small curated demo set, but they do not scale. New meme tokens appear constantly, and the project should not become data-entry work.

### Step 3A — Paste mint

Let the user paste a Solana token mint.

The app should try to resolve:

- token symbol
- token name
- decimals
- price/reference data if available
- Jupiter quote
- Raydium quote
- Phantom quote where supported
- other venues only when honest support exists

Curated venues remain curated:

- Orca only if a real pool candidate exists
- Meteora only if a real DLMM pool candidate exists
- PumpSwap only if a real curated pool exists

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

After Jupiter execution works, evaluate and gradually add additional execution paths only where technically honest and worth it.

### Possible order

1. Raydium execution path
2. Orca execution path
3. Meteora DLMM execution path
4. PumpSwap execution or handoff path if strategically useful
5. Phantom comparison/handoff path if measurable and honest

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
- Jupiter execution works
- quote-only routes are clearly labeled
- token intake has at least paste-by-mint support or a strong curated set
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

Near-term: Jupiter owns the executable recommendation path.

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

### Session 1 — route testing and comparison review

Start server and test:

- SOL → USDC
- SOL → BONK
- SOL → WIF
- SOL → POPCAT
- SOL → CHAD
- SOL → SPX6900
- SOL → FIGURE

Inspect:

- which venues produce cards
- which venues fail softly
- whether the recommended route makes sense
- whether the direct route makes sense
- whether alternatives are readable
- whether cost lines are understandable
- whether quote-only/non-clickable status is clear

Goal:

**confirm the current engine and cards reflect the mission.**

---

### Session 2 — decision UX cleanup

Improve:

- route-card wording
- estimated cost wording
- quote-only labels
- unsupported venue diagnostics
- recommendation explanation
- direct-route explanation
- visible vs expanded details

Goal:

**make the route cards clear enough to build execution on top.**

---

### Session 3 — prepare Jupiter execution plan

Plan the first executable flow:

- selected Jupiter quote
- confirmation state
- Phantom signing
- transaction sending
- result state
- error handling

Goal:

**enter the Jupiter execution sprint with a clear technical plan.**

---

## Next major milestone

**Swap Transparency Alpha**

A credible local alpha where a user can:

1. connect Phantom
2. choose a swap pair and amount
3. see a reference/benchmark comparison
4. compare real quote universes
5. understand which route is recommended and why
6. understand known costs and unknowns
7. execute the recommended Jupiter route through Phantom
8. trust that unsupported routes are not being faked

---

## Resume point

Start next session from:

**route testing and comparison review.**

First action:

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --log-level debug

Future dashboard / activity layer:
Evaluate Helius getTransfersByAddress for parsed wallet transfer history, activity feed, and support-mode diagnostics.

Resume Web3 Digest from commit d945454.

Current milestone:
External Token Flow V1 is working and committed:
- paste Solana mint in /ui
- resolve metadata via DexScreener
- resolve decimals via Solana RPC
- quote temporary external tokens without TOKEN_META mutation
- Jupiter/Raydium/Meteora/Orca/Phantom coverage works
- PumpSwap canonical pool discovery works for SOL <-> pump-style token pairs
- token promotion audit tool works and reports readable universe diagnostics
- latest commit: d945454 Polish token promotion audit reporting
- tests: 130 OK
- git status was clean

Next session:
1. Run git status/log/tests.
2. Do live UI checks for SOL -> Fartcoin and SOL -> USDUC.
3. Decide between:
   A) productize external-token UI/promotion audit display,
   B) update docs/roadmap/technical deep dive for External Token Flow V1,
   C) plan Helius activity layer for future wallet dashboard/support diagnostics.
Future idea: evaluate Helius getTransfersByAddress for parsed wallet transfer history, activity feed, and support-mode diagnostics.
