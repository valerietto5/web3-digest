# Roadmap — Web3 Digest

This file is the active “where we’re going next” plan for Web3 Digest.

It should stay clean enough to use as the main resume/start point at the beginning of each session.

Updated checkpoint: after guarded execution paths for Jupiter, Raydium, Orca, PumpSwap, Meteora single-pool execution, recognized external-token swaps, swap cost/token stats diagnostics, and the beginning of the Frontend / UX Design V1 chapter.

Latest implementation checkpoints reflected here:

- `0f3f15a` — Fix Orca native SOL wrapping
- `343a2ba` — Support recognized external token swaps
- `0510101` — Improve swap token modal and post-swap UX
- `0d533b1` — Improve swap cost and token stats diagnostics

---

## Current phase

**Execution Intelligence Alpha → Frontend / UX Design V1**

Web3 Digest is no longer being treated as “a wallet that can also do swaps.”

It is now clearly a:

**Solana swap-intelligence product with guarded execution.**

That means:

- Phantom remains the wallet, signer, and security layer
- Web3 Digest becomes the place where users:
  - connect wallet
  - preview a swap
  - compare recognizable execution universes
  - understand benchmark/reference gap
  - understand known route costs where available
  - review token stats and holder concentration
  - choose better execution paths
  - execute supported routes through Phantom

The product wedge is:

**connect Phantom, compare swap outcomes honestly, explain costs clearly, inspect token context, then execute supported routes safely.**

The engine/product thesis is now proven enough locally.

The next big chapter is:

**Frontend / UX Design V1**

The goal is to turn the current working swap terminal into a cleaner, more compact, more mobile-first, more visually distinctive product surface.

---

## Product identity

**Web3 Digest is an execution-intelligence layer for swaps, wrapped in a wallet-connected experience.**

### Mission

Help people make better swaps by making execution transparent, understandable, and low-cost.

### Vision

Build the most trusted, user-friendly swap experience in crypto — simple enough for non-crypto natives, transparent enough for power users.

### Purpose

Protect users from blind execution, hidden wallet-layer costs, poor route transparency, and unclear token context.

### Direction

Compare multiple execution universes, execute supported routes through Phantom, expand scalable token intake, improve cost modeling, improve token/risk context, and later evaluate broader venue/multichain execution intelligence.

### Moat

We make execution understandable, trustworthy, and cost-transparent — and we let users compare meaningful alternatives instead of executing blindly.

### North star

**Make swaps feel free:** no hidden wallet tax, radically transparent costs, and execution that minimizes total user cost as much as possible.

### One-line pitch

**Web3 Digest helps users compare swap routes, understand costs, inspect token context, and choose the best execution with no hidden wallet-layer markup.**

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
- external token import/token modal
- post-swap success state and balance refresh
- cost explanation and route/reference gap display
- token stats & holder concentration section
- Bubblemaps link and holder diagnostics
- tests covering registry, quote, prepare, preflight, execution gating, external-token behavior, token stats, and PumpSwap diagnostics

### Current quote universes

The quote engine now compares multiple recognizable execution universes.

#### Jupiter

- quote + executable through Phantom
- used for primary reference/recommendation behavior where it wins
- USDC -> SOL preflight passed and opened Phantom during reverse-route testing
- used successfully for external-token swaps where supported

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

- DLMM quote path and single-pool execution path where supported
- Meteora Panini -> SOL executed successfully on Solana mainnet
- still limited and guarded; not a broad composed execution engine yet
- no fake DLMM candidates

#### Phantom

- wallet-routing quote research surface
- comparison-only
- non-clickable
- benchmark-only in the current preview path
- Phantom route legs are not treated as Web3 Digest executable routes

#### PumpSwap

- direct SOL <-> pump-token quote + execution where a canonical/direct pool is discovered
- PumpSwap direct coverage is not a composed route engine yet
- SNP500 -> SOL executed successfully on Solana mainnet
- SOL -> KINS executed successfully on Solana mainnet
- MATCH investigation clarified that a token may have Pump.fun AMM liquidity but not a direct SOL <-> token canonical pool
- known DexScreener/Pump AMM pair addresses can now be passed into PumpSwap quote helper as audit candidates
- if a known pool exactly matches the requested direct pair, it can quote safely through the SDK
- if a known pool is non-SOL/multi-hop, it fails soft with diagnostics such as `TOKEN_NOT_DIRECT_SOL_PAIR`
- Jupiter’s Pump.fun AMM route legs remain distinct from standalone PumpSwap

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

Validated external-token behavior includes:

- SNP500: `3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump`
- AIX
- Panini
- KINS
- MATCH

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

Phantom remains non-clickable unless a real handoff path is implemented.

Meteora/PumpSwap/Raydium/Orca/Jupiter are clickable only through guarded readiness/capability/variant checks.

### Ranking remains honest

Ranking is based on actual quoted receive amount.

Do not manipulate ranking to make a venue look better.

### Curated means curated

Curated pool/venue support should not be generalized unless the backend can support it honestly.

### Solana first

The current wedge is Solana swap execution transparency.

Multichain expansion comes later only after the Solana wedge is strong.

### Frontend design must not break swap logic

The Frontend / UX Design V1 chapter should focus on layout, visual hierarchy, compactness, colors, shapes, responsive behavior, and product clarity.

During frontend design work:

- do not change route ranking
- do not change provider behavior
- do not change execution gates
- do not change token resolution
- do not change Phantom benchmark-only behavior
- do not add execution behavior unless explicitly scoped

---

## Current product assessment

The engine now reflects the product mission.

It can show that a swap is not one invisible black-box price. It can compare multiple execution universes, show which ones succeed, show which ones fail, explain the value gap vs reference, show app fee transparency, expose token stats, and avoid pretending unsupported venues work.

Current status:

| Area | Status |
|---|---|
| Multi-universe quote engine | Strong alpha |
| Token coverage | Curated + dynamic pasted-mint Alpha |
| Cost transparency | Implemented V1, needs visual polish |
| Token stats / holder concentration | Implemented V1, needs visual polish |
| Recommendation display | Working, needs frontend redesign |
| Execution | Working alpha for Jupiter, Raydium, Orca, Meteora single-pool, PumpSwap direct |
| Final UI | Not ready yet |
| Public beta | Not ready yet |

Current conclusion:

**The product thesis is proven. The next work is frontend/UX design, product clarity, mobile-first polish, and controlled alpha hardening.**

---

# Macro roadmap

## Phase 0 — Baseline UI / Execution Intelligence Cleanup

### Status

**Mostly complete / shipped locally.**

This phase included the work that made the app usable enough to start visual design.

### Shipped work

- route cards simplified
- Recommended / Direct / Alternatives structure clarified
- Phantom benchmark-only behavior clarified
- Swap cost wording improved
- `Swap cost:` label added
- route difference vs reference added
- `App fee: $0.00` added
- expanded cost explanation added:
  - swap cost is the value gap between reference market price and route expected output
  - it may reflect price impact, spread, route quality, quote movement, or reference-price uncertainty
  - it is not a separate Web3 Digest fee
- Token stats & holder concentration added
- market stats row added from available quote/reference metadata:
  - Liquidity
  - 24h volume
  - FDV
  - Mkt cap
- missing market values are omitted instead of shown as fake `$0.00`
- Bubblemaps link preserved
- holder diagnostics preserved
- token modal improved
- zero balances hidden
- external mint import improved
- post-swap balance refresh implemented
- diagnostics collapsed by default
- PumpSwap/MATCH diagnostics clarified

### Current checkpoint

Latest pushed commit:

`0d533b1` — Improve swap cost and token stats diagnostics

---

## Phase 1 — Frontend / UX Design V1

### Goal

Turn the current working swap terminal into a visually coherent, compact, mobile-first product surface.

The product should feel:

- Phantom-inspired
- warm
- colorful
- rounded
- compact
- token-native
- fun but trustworthy
- not cold institutional DeFi
- not casino/trading-scam
- not generic black crypto dashboard

### Core design principle

**Phantom warmth + intelligent swap comparison.**

Web3 Digest should feel like a wallet-native swap assistant, not a developer dashboard.

---

## Phase 1A — Arsenal / design workflow

This design chapter uses a multi-tool workflow.

### ChatGPT — product/design director

Role:

- product direction
- design strategy
- prompt architect
- implementation planner
- roadmap keeper

Responsibilities:

- define product/design constraints
- protect swap logic
- decide what belongs now vs later
- translate visual ideas into engineering tasks
- write prompts for Stitch / Claude / Codex
- help update `ROADMAP.md`

Rule:

ChatGPT orchestrates the design process, but does not act as the only visual designer.

---

### Google Stitch — fast visual exploration lab

Role:

- AI visual exploration tool

Responsibilities:

- generate visual directions
- generate palette systems
- compare dark/light mode pairs
- explore mobile-first screen concepts
- quickly test Phantom-inspired, Apple-soft, and token-native directions

Rules:

- use Stitch for visual references, not production code
- do not let Stitch change product logic
- do not copy Stitch code directly into the repo
- keep asking Stitch for controlled variants, not random full redesigns

Current Stitch status:

- first mobile swap concepts generated
- palette options generated
- current finalists:
  - Option A — Midnight Blue
  - Option G — Emerald Pop
- discarded:
  - Option C
  - Option D
  - H as too premium/serious
  - F uncertain / not finalist

Next Stitch action:

Clean the board and keep/refine only A and G, showing dark and light modes for both.

---

### Figma — design source of truth

Role:

- design board and source of truth

Responsibilities:

- organize screenshots and references
- store selected Stitch outputs
- compare A/G finalists
- define design tokens
- create mobile and desktop mockups
- organize route card / token stats / diagnostics components
- prepare visual handoff for Codex

Rules:

- Figma is for visual decisions and handoff
- do not use Figma-to-code as production source
- use Figma to define what Codex should build

Planned Figma file:

`Web3 Digest Frontend Design V1`

Planned pages/frames:

- Current UI screenshots
- Phantom references
- LlamaSwap references
- Stitch A/G finalists
- Design tokens
- Mobile swap terminal
- Desktop/web swap terminal
- Route card component
- Token stats component
- Advanced diagnostics component
- Light mode
- Dark mode

---

### Claude — senior design critic / reviewer

Role:

- design critic and alternate perspective

Responsibilities:

- critique Stitch/Figma outputs
- compare A vs G
- identify what feels too generic, too serious, too crowded, or too banking-like
- suggest visual hierarchy improvements
- review before Codex implementation

Rules:

- do not let Claude rewrite product logic
- do not let Claude generate final production code
- use Claude for critique, not execution

Example Claude use:

Ask Claude to critique A/G like a senior crypto product designer and recommend which direction feels more Web3 Digest.

---

### Codex — frontend implementation engineer

Role:

- implementation engineer inside the repo

Responsibilities:

- implement CSS/design tokens
- refactor layout safely
- update `api/ui_page.py`
- preserve swap logic
- run tests
- commit/push only when instructed

Rules:

- no swap logic changes unless explicitly requested
- no provider changes during design work
- no route ranking changes
- no execution behavior changes
- no `.env` or wallet runtime files staged
- frontend-only unless clearly scoped

---

## Phase 1B — Visual direction exploration

### Status

**In progress.**

### Current finalists

#### Option A — Midnight Blue

Strengths:

- best overall foundation
- readable
- premium
- crypto-native
- easy on the eyes
- strong dark mode candidate

Risks:

- could become too safe/serious if not given enough playful accent energy

#### Option G — Emerald Pop

Strengths:

- distinctive
- fresh
- less common than blue/purple crypto UI
- improved version of the earlier green direction

Risks:

- could become too banking/finance-like if not made playful enough

### Discarded / deprioritized

- Option C — discarded
- Option D — discarded
- H — too premium/serious
- F — uncertain, not finalist
- generic cute AI blob mascot — rejected

### Next action

Ask Stitch to clean/refine only:

- Option A — Midnight Blue
- Option G — Emerald Pop

Both should show:

- dark mode
- light mode
- same layout and hierarchy
- production-ready polish
- no mascot yet

---

## Phase 1C — Brand identity research

### Status

**Upcoming.**

Brand identity is related to frontend design, but it is not the same as implementation.

Brand identity includes:

- color world
- shape language
- logo/icon direction
- mascot or no mascot
- token icon treatment
- button personality
- card personality
- light/dark personality
- emotional feel

### Current direction

Web3 Digest should feel:

- friendly
- compact
- colorful
- route-intelligent
- token-native
- fun but trustworthy

It should not feel:

- generic black crypto app
- serious DeFi dashboard
- banking app
- casino/trading scam
- childish toy app

### Mascot research

Mascot is a separate brand research track.

Current mascot decisions:

- do not force mascot into the main swap UI now
- reject generic cute AI blob
- mascot should not dominate the product surface
- mascot should communicate:
  - route-finding
  - digesting complexity
  - swap intelligence
  - small-token/meme-token culture
  - friendly but trustworthy

Possible future mascot placements:

- loading state
- empty state
- success state
- small header mark
- educational tooltip
- route explanation helper
- token safety/context tips

Mascot research is planned as a separate weekend/future session.

---

## Phase 1D — Design system / tokens

### Status

**Upcoming after A/G direction is chosen or narrowed.**

Goal:

Turn the chosen visual direction into reusable design rules.

Design tokens to define:

- main background
- surface background
- card background
- soft card background
- primary accent
- secondary accent
- success color
- warning color
- danger color
- text primary
- text secondary
- border color
- card radius
- button radius
- pill radius
- shadow/glow style
- spacing scale
- font sizes
- mobile breakpoints

Example tokens:

```css
--bg-main
--bg-surface
--bg-card
--bg-card-soft
--accent-primary
--accent-secondary
--text-main
--text-muted
--success
--warning
--danger
--radius-card
--radius-pill
--shadow-card

Design-token rule:

Do not let CSS become random one-off styling. Build a small Web3 Digest design system.

---

## Phase 1E — Figma mockups / design board

### Status

**Upcoming.**

### Goal

Create enough visual clarity that Codex can implement without inventing design.

### Mockups needed

- mobile swap terminal
- desktop/web swap terminal
- dark mode
- light mode
- Recommended route card
- Direct route card
- Alternatives section
- Token stats & holder concentration card
- Advanced diagnostics collapsed
- quote loading
- quote expired
- success state

### Output

A practical visual source of truth, not necessarily perfect pixel-perfect design.

---

## Phase 1F — Claude design critique

### Status

**Upcoming after Figma/Stitch finalists are organized.**

Claude should review:

- Option A
- Option G
- Figma board
- Phantom references
- LlamaSwap references
- Web3 Digest design brief

Questions for Claude:

- Which direction feels more Web3 Digest?
- Which direction is too serious?
- Which direction is too generic?
- Which one has stronger mobile UX?
- Does the UI feel Phantom-inspired without copying Phantom?
- Does the UI feel fun but trustworthy?
- What should change before engineering implementation?

### Output

- accepted critique
- rejected critique
- implementation notes for Codex

---

## Phase 1G — Codex frontend implementation batches

### Status

**Upcoming after design direction/tokens/mockup are ready.**

Implementation should be safe and incremental.

### Batch 1 — CSS tokens + base shell

Scope:

- CSS variables
- page background
- typography scale
- card surfaces
- button style
- radius/shadow/glow
- base light/dark mode structure if ready

No swap logic changes.

### Batch 2 — Swap terminal layout

Scope:

- You Sell card
- You Buy card
- token selector pills
- amount display
- balance/MAX/50%
- Preview Quote CTA
- compact mobile-first spacing

No provider logic changes.

### Batch 3 — Route cards redesign

Scope:

- Recommended route
- Direct route
- Alternatives
- Phantom benchmark-only card
- cost line
- below/above reference line
- App fee line
- expanded cost explanation

No route ranking changes.

### Batch 4 — Token stats + diagnostics polish

Scope:

- Liquidity / 24h volume / FDV / Mkt cap row
- holder concentration row
- Bubblemaps
- holder diagnostics
- advanced diagnostics collapsed
- raw JSON visually quieter

No backend token/risk scoring changes unless separately scoped.

### Batch 5 — Responsive/mobile pass

Scope:

- mobile widths
- desktop widths
- spacing
- overflow
- tap targets
- card stacking
- sticky actions if useful

### Batch rules

Each batch must:

- preserve swap logic
- preserve execution gates
- preserve provider behavior
- preserve Phantom benchmark-only behavior
- run tests
- smoke test UI
- avoid live execution unless explicitly requested
- avoid committing until stable and instructed

---

## Phase 1H — QA and iteration

### Status

**Upcoming.**

Frontend QA must test product states, not just unit tests.

States to test:

- no wallet connected
- wallet connected
- known token
- external pasted token
- quote loading
- quote expired
- recommended route
- direct route
- alternatives
- no quote
- provider errors
- token stats available
- token stats unavailable
- holder data unavailable
- holder data partial
- preflight passed
- preflight failed
- success state
- mobile layout
- desktop layout
- light mode
- dark mode

Success criteria:

- a normal user can understand the main swap screen in 10 seconds
- route cards are easy to scan
- token stats are visible but not scary
- diagnostics are available but visually quiet
- UI feels mobile-first and polished
- no execution behavior regresses

---

## Phase 2 — Guarded Execution Through Phantom

### Goal

Keep the shipped execution paths honest, safe, and debuggable.

This is the phase where Web3 Digest became more than an analysis tool.

### Scope

- Jupiter, Raydium, Orca, Meteora single-pool, and PumpSwap direct paths are executable where supported
- Phantom remains the signing boundary
- user approves in wallet
- app sends/broadcasts the transaction
- app preflights before Phantom and shows confirmation or translated error
- unsupported or quote-only routes remain non-clickable

### Work

- keep live-testing small swaps when needed
- harden prepared-transaction preflight diagnostics
- keep SOL setup/rent/fee checks conservative and explainable
- improve stale-balance / post-swap refresh UX
- preserve user approval in Phantom
- show transaction result and explorer links clearly
- keep Phantom non-clickable until a real handoff path exists

### Product rule

Do not make a route executable unless prepare, preflight, Phantom signing, and backend submit are all real for that provider/variant.

---

## Phase 3 — Scalable Token Intake

### Goal

Stop relying on manual token additions.

Manual token additions are useful for a small curated demo set, but they do not scale. New meme tokens appear constantly, and the project should not become data-entry work.

### Step 3A — Paste mint

Status: **shipped as Alpha.**

Let the user paste a Solana token mint.

The app should try to resolve:

- token symbol
- token name
- decimals
- price/reference data if available
- Jupiter quote/execution where supported
- Raydium quote/execution where supported
- Orca quote/execution where supported
- Meteora quote/execution where supported
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
- non-SOL Pump.fun AMM pools can be audited from known pair addresses without faking standalone PumpSwap routes

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

1. Meteora execution expansion beyond current single-pool support
2. composed PumpSwap token -> SOL -> USDC style routes
3. broader external-token route discovery
4. Phantom comparison/handoff path if measurable and honest
5. additional Solana venues only when prepare/preflight/submit are real

### Product rule

Execution expansion should be careful.

Do not make a universe clickable until the app can really execute or hand off that exact path.

---

## Phase 5 — Private Alpha Readiness

### Goal

Make Web3 Digest usable by someone who is not us.

This is where the product should become cleaner, mobile-aware, and ready for small external testing.

### Work

- finish Frontend / UX Design V1
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
- Jupiter/Raydium/Orca/Meteora/PumpSwap execution paths remain stable in small live tests
- quote-only routes are clearly labeled
- token intake has paste-by-mint support and clear unresolved-decimals behavior
- token stats and cost explanations are understandable
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

### Current user-facing wording

Visible card wording should stay simple:

- `Swap cost:`
- `~0.97% below reference`
- `App fee: $0.00`

Expanded explanation:

**Swap cost is estimated as the value gap between the reference market price and the route’s expected output. It may reflect price impact, spread, route quality, quote movement, or reference-price uncertainty. It is not a separate Web3 Digest fee.**

### Product rule

Do not invent precision.

If a cost is not known, say it is unavailable or not disclosed.

---

## Token stats / holder concentration direction

The token context layer should stay objective.

It should not say:

- safe
- unsafe
- scam
- rug
- low risk
- high risk

Current user-facing direction:

- `Token stats & holder concentration`
- `Liquidity`
- `24h volume`
- `FDV`
- `Mkt cap`
- `Top holder`
- `Top 5`
- `Top 10`
- `Open Bubblemaps`
- `Holder diagnostics`
- `Distribution only — not a safety score.`

### Product rule

Make risk/context signals visible before the user clicks, but do not pretend to produce a safety verdict.

---

## Route-card structure

The route-choice structure remains:

- Recommended
- Direct
- Alternatives

### Recommended

Best current executable route, or best quote clearly marked if non-executable.

Executable recommendations can come from any currently supported executable provider: Jupiter, Raydium, Orca, Meteora single-pool, or PumpSwap direct SOL <-> pump-token paths.

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

### Session 1 — Stitch A/G finalist cleanup

Use Stitch to clean the exploration board and keep/refine only:

- Option A — Midnight Blue
- Option G — Emerald Pop

Goal:

**choose or narrow the main Web3 Digest visual direction.**

---

### Session 2 — Brand identity / mascot research

Explore mascot and brand identity separately from the main swap UI.

Goals:

- reject generic cute AI blob direction
- explore mascot concepts that communicate route-finding, digesting complexity, swap intelligence, and token-native fun
- decide whether mascot belongs in:
  - logo/icon
  - loading state
  - success state
  - educational helper
  - header
- avoid forcing mascot into the main swap card too early

---

### Session 3 — Figma setup and design board

Create Figma source-of-truth board:

- current UI screenshots
- Phantom references
- LlamaSwap references
- Stitch A/G finalists
- early design tokens
- mobile frame
- desktop frame

Goal:

**move from visual exploration into structured design handoff.**

---

### Session 4 — Claude critique

Ask Claude to critique the selected visual direction and Figma/Stitch outputs.

Goal:

**get a senior design-review pass before Codex implementation.**

---

### Session 5 — ROADMAP + Codex implementation planning

Turn the final design direction into frontend implementation batches.

Goal:

**prepare the first Codex prompt for design tokens and base shell implementation.**

---

## Next major milestone

**Frontend / UX Design V1**

A credible local alpha where a user can:

1. connect Phantom
2. choose a swap pair and amount
3. see a compact, polished mobile-first swap terminal
4. see a reference/benchmark comparison
5. compare real quote universes
6. understand which route is recommended and why
7. understand known costs and unknowns
8. inspect token stats and holder concentration
9. execute supported Jupiter/Raydium/Orca/Meteora/PumpSwap routes through Phantom
10. trust that unsupported routes are not being faked

---

## Resume point

Start next session from:

**Frontend / UX Design V1 — Stitch A/G finalist cleanup.**

Immediate action:

Ask Stitch to clean and refine only:

- Option A — Midnight Blue
- Option G — Emerald Pop

Then decide whether A, G, or an A/G hybrid becomes the main visual direction.

Future dashboard / activity layer:

Evaluate Helius parsed transfer history for wallet activity feed and support-mode diagnostics after the swap wedge and frontend V1 are stable.