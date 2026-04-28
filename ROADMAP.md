# Roadmap (Weekly / Monthly)

This file is the active “where we’re going next” plan for Web3 Digest.  
Updated weekly on Friday, but it should stay clean enough to use as the main resume/start point at the beginning of each session.

---

## Current phase

**Swap Transparency V1.5 is the active build phase.**

Web3 Digest is no longer being treated primarily as “a wallet that can also do swaps.”

It is now clearly a:

**wallet-connected execution-transparency app**

That means:

- Phantom remains the wallet, signer, and security layer
- Web3 Digest becomes the place where users:
  - connect wallet
  - preview a swap
  - compare recognizable execution universes
  - understand benchmark gap vs explicit costs
  - make better execution decisions
  - later get a stronger connected dashboard experience

The product wedge is now much more precise:

**connect Phantom, compare swap outcomes honestly, explain costs clearly, then expand the connected experience later.**

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
Compare multiple execution universes first, then expand into stronger explicit-cost modeling, more venues/providers, better route intelligence, and later multichain execution intelligence.

### Moat
We make execution understandable, trustworthy, and cost-transparent — and we let users compare meaningful alternatives instead of executing blindly.

### North star
**Make swaps feel free:** no hidden wallet tax, radically transparent costs, and execution that minimizes total user cost as much as possible.

### One-line pitch
**Web3 Digest helps users compare swap routes, understand costs, and choose the best execution with no hidden wallet-layer markup.**

---

## What is shipped locally

The current local build now includes real progress well beyond the original Jupiter-only prototype.

### Core app / UI foundation
- FastAPI backend
- browser UI at `/ui`
- live quote-preview surface
- inline benchmark/reference updates while typing
- Recommended + Direct + Alternatives structure
- improved quote hierarchy and cleaner route surface
- CTA skeleton for Recommended and Direct
- wallet-connected / Phantom-oriented product framing

### Benchmark layer
- quote-time benchmark resolver skeleton added
- explicit benchmark source slots added for:
  - major/canonical source
  - Solana-native source
  - long-tail source
  - SQLite fallback
- Jupiter Price API V3 added as the first real Solana-native benchmark source
- CoinGecko remains fallback
- SQLite remains final fallback
- UI transparency/source block now explicitly supports:
  - `jupiter_price_v3`
  - `coingecko_simple_price`
  - `sqlite_usd_snapshots`

### Cost-model progress
- `execution_cost_usd` fixed so Recommended now uses a real USD value
- route-fee disclosure semantics improved:
  - disclosed no longer means only “fully priceable in USD”
- current breakdown can show:
  - execution cost
  - network cost
  - route fees
- benchmark comparison and route-card cost semantics were clarified conceptually

### Future-facing card model prep
The option/card model now supports:
- `execution_surface_label`
- `is_comparison_only`
- `is_clickable`

The UI now respects those fields while preserving current behavior.

### First non-Jupiter universe
**Raydium is now live locally as the first honest non-Jupiter comparison universe.**

Current Raydium state:
- quote-only
- comparison-only
- non-clickable
- appears locally as Alternative 1
- does not replace Jupiter Recommended / Direct yet

This is the first real step toward the longer-term multi-universe execution-aggregator vision.

---

## Current real checkpoint

The product is no longer only:
- Jupiter plus internal Jupiter route variants

It is now beginning to act like:
- Jupiter as main executable universe
- Raydium as first non-Jupiter comparison universe
- benchmark layer with more honest source handling
- cost layer with improved truthfulness
- future-ready card model for recognizable execution surfaces

So the current build is no longer “just a demo quote surface.”

It is becoming the first honest version of:
**a recognizable execution-comparison product.**

---

## Locked product rules

These are now active and should remain stable unless intentionally changed later.

### Identity
Web3 Digest is a **wallet-connected execution-transparency app**, not a Phantom replacement wallet.

### Core value
Help users compare execution options, understand costs and tradeoffs, and make better swap decisions.

### Trust philosophy
- do not invent precision
- do not hide the cost story
- do not fake venue distinctions
- do not claim superiority without declared scope

### Execution philosophy
Compare first.  
Explain clearly.  
Execute later with trust.

### Ecosystem focus
Solana first.  
Expand later only after the wedge is genuinely strong.

### Product focus
Swap is the wedge.  
Wallet infrastructure supports it.  
Dashboard/holdings work remains secondary unless it improves trust, execution, or support quality.

---

## Locked cost-model direction

### Cost model split
This is now conceptually locked:

- **Left panel = benchmark comparison**
- **Route cards = explicit costs**

These should not be treated as the same layer of truth.

---

### 1. Left panel = benchmark comparison layer

This panel explains the route against the theoretical/reference benchmark.

Conceptually it should show:
- **You pay**
- **Ideal reference**
- **Real vs ideal gap**

Purpose:
- preserve route-quality transparency
- explain how the executable quote compares to the benchmark
- avoid pretending the benchmark gap is literally the same thing as a fee

This is the **comparison/transparency layer**, not the final explicit-fee box.

---

### 2. Route cards = explicit cost layer

The route cards should move toward showing **real explicit costs** for that route/universe choice.

Long-term target for cards:
- **Estimated explicit cost**
- expandable breakdown:
  - **Execution cost** (while transitional model remains)
  - **Network cost**
  - **Route fees**
  - **Platform fee** when real/disclosed and modeled honestly

Purpose:
- show actual known route-level costs
- keep the fee layer separate from the benchmark-comparison layer
- avoid permanently mixing benchmark shortfall with explicit transaction costs

---

### Transitional rule for the current build
For now, some current wording such as:

- **Estimated total swap cost**

may remain while backend logic continues to evolve.

That is acceptable short-term, but it is **not** the final conceptual destination.

Long-term direction:
- left panel keeps benchmark comparison
- route cards evolve toward explicit-cost framing

---

### Meaning of current cost lines

#### Execution cost
Current user-facing meaning:
- how much worse the executable swap is than the benchmark/reference baseline

This is currently part of the route-card cost story, but conceptually it belongs to the broader comparison layer, not the same category as explicit chain/platform fees forever.

#### Network cost
Current user-facing meaning:
- estimated on-chain transaction cost required to perform the swap

#### Route fees
Current user-facing meaning:
- fees disclosed by the route/quote itself

If not disclosed clearly:
- show **Route fees: not disclosed for this swap**
- do not fabricate a numeric fee

---

### Current implementation rules
Backend returns separated fields for the recommended route:

- `execution_cost_usd`
- `network_cost_usd`
- `route_fees_usd` or `null`
- `route_fees_disclosed`
- `estimated_total_swap_cost_usd`

Rules:
- `estimated_total_swap_cost_usd` = sum of known numeric components only
- if route fees are not disclosed/priceable, they are not fabricated
- disclosed and priceable are not treated as the same thing anymore

---

## Locked transparency vs cost separation

These two ideas stay distinct:

### Transparency question
**“How does the executable quote compare to the fresh benchmark/reference?”**

Answered by:
- the left panel / benchmark gap layer

### Cost question
**“What are the known route-level costs of doing this swap?”**

Answered by:
- the route-card cost box

This separation is now locked.

---

## Locked route-choice structure

The route-choice structure remains:

- **Recommended**
- **Direct**
- **Alternatives**

This structure stays. What evolves is:
- how those roles are assigned
- which universes fill them
- how they are labeled

---

## Locked interaction model

### Button vs whole-card tap
CTA stays a **button**, not whole-card click.

### Expand vs execute
These remain separate behaviors:
- **Expand** = inspect details
- **Execute** = begin swap action

### Execution sequencing
Current intended actionability order:
1. Recommended
2. Direct
3. Alternatives later

This remains fine for the current phase.

### CTA wording
Current working wording:
- Recommended: **Swap this route**
- Direct: **Try direct route**

Alternatives remain secondary and currently do not need executable CTA first.

### CTA placement
Current desktop/web placement rule:
- top-right area of the inner card
- visually attached to the card
- not whole-card tap
- not hidden inside expanded details

---

## Locked comparison-universe direction

### Core idea
Web3 Digest should evolve toward comparing a small set of **real, recognizable execution universes** and fitting them into the existing card structure.

The goal is to make the value obvious to the user.

Instead of only seeing abstract internal route labels, the product should increasingly let the user understand:

- what they get **via Jupiter**
- what they get **via Raydium**
- what they may later get **via Meteora**
- what they may later get **via Phantom swap flow**

This is what makes Web3 Digest feel like:
**an honest and intelligent execution aggregator**

---

## Locked comparison universes (V1 direction)

### Jupiter
- aggregator execution universe
- fully real
- executable universe

### Raydium
- real non-Jupiter universe
- currently quote-only and comparison-only in the app
- long-term intended as executable universe once appropriate path is added

### Meteora
- future venue-restricted executable universe
- not integrated yet
- must only be added through a real Meteora-native or Meteora-restricted quote path

### Phantom
- user-facing comparison surface / anchor
- comparison-only in V1
- should not be faked through guesses or assumed penalties

---

## Honest universe-fetching rules

No fake universes.

A universe should only appear as its own card if the backend can explain:
- what that universe means technically
- how the quote was obtained honestly

### Jupiter rule
Use real Jupiter quote data.

### Raydium rule
Use a real Raydium quote path, not a generic aggregator route relabeled as Raydium.

### Meteora rule
Must come from a real Meteora-native or Meteora-restricted quote path.

### Phantom rule
Should remain comparison-only until there is:
- a truly measurable Phantom path
or
- a clearly justified proxy

---

## Locked card assignment logic

Cards are **roles**, not fixed brands.

### Recommended
Best executable result among the real executable universes.

Current/future executable universe set:
- Jupiter
- Meteora later
- Raydium later when execution-capable lane is ready

Primary rule:
- best economic result / best receive

### Direct
Simplest meaningful executable option among the real executable universes.

Primary rule:
- fewer steps
- simpler / more inspectable execution
- if tied, prefer better output

Direct is not “second best.”  
It is the **simplest credible executable lane**.

### Alternative 1
Best remaining executable or comparison candidate not already used by Recommended or Direct.

### Alternative 2
Always Phantom later.

Role:
- comparison-only
- non-clickable
- user-recognizable anchor

---

## Locked wording direction

Default visible card wording should increasingly prioritize the **user-facing execution surface**, not internal route/provider names.

Future preferred visible wording:
- **Via Jupiter**
- **Via Raydium**
- **Via Meteora**
- **Via Phantom**

Internal route/provider names such as:
- BisonFi
- HumidiFi
- Scorch
- Quantum
- etc.

should move into:
- expanded details
- inspect mode
- raw route breakdowns

This is one of the main next-step cleanup tasks because the product now includes more than one real universe.

---

## Current UI / UX direction

### Top swap module
Still conceptually locked as:
- network header
- sell panel
- buy panel
- invert control
- main action row
- compact benchmark/transparency block

### Lower route-choice surface
Still conceptually split into:
- Recommended
- Direct
- Alternatives

But now the route-choice surface is beginning to represent:
- not just route variants
- but distinct comparison universes

That is a meaningful shift in product meaning.

---

## What is still transitional

The current build is meaningful, but not final.

Still transitional:
- card wording still leans too much on internal route/provider labels
- Raydium is still comparison-only
- Phantom is not surfaced yet
- Meteora is not integrated
- Direct assignment is still effectively Jupiter-centered in practice
- Jupiter timestamp semantics still need future truthfulness cleanup
- explicit-cost model is still transitional and not yet the final pure venue-cost layer
- token support is still narrow

---

## What is deprioritized for now

The connected dashboard, holdings display, and wallet-cockpit layer are still useful, but they are **not** the lead wedge.

Those pieces should be worked on when they support:
- trust
- execution
- post-swap understanding
- support/debugging
- connected identity quality

They should not pull the project away from the core priority:

**swap transparency first.**

---

## Next week plan

### Monday — card wording / surface-label cleanup
Focus:
- move visible card language further toward user-facing execution surfaces
- reduce reliance on internal route labels such as:
  - BisonFi
  - HumidiFi
  - Scorch
  - Quantum
- make the product more immediately understandable as:
  - Via Jupiter
  - Via Raydium

Goal:
- make the live local Jupiter + Raydium comparison more legible to real users

---

### Tuesday — Raydium stabilization / cleanup
Focus:
- verify Raydium comparison lane stays stable
- inspect any edge cases in alternative-slot rendering
- review the future UI filter issue discovered during debugging:
  - other_options can be hidden client-side when `route_label` collides with Recommended
- keep Raydium comparison-only and non-clickable for now

Goal:
- make the first non-Jupiter universe feel reliable and intentionally placed

---

### Wednesday — Meteora feasibility research
Focus:
- define what “Via Meteora” would mean technically
- determine whether there is a real Meteora-native or Meteora-restricted quote path
- decide whether Meteora is the next honest universe after Raydium

Goal:
- decide whether Meteora becomes the next universe to normalize into the shared option model

---

### Thursday — Meteora normalized-model planning (if feasible)
If Meteora is feasible:
- map Meteora quote data into the shared option/card model
- decide comparison-only vs executable-first initial scope

If Meteora is not ready:
- continue wording cleanup
- continue Raydium cleanup
- or review benchmark timestamp truthfulness

Goal:
- leave the week with a clear path for the next universe after Raydium

---

### Friday — docs / checkpoint / weekly cleanup
Focus:
- update ROADMAP.md cleanly
- tighten README / SHIPPED / technical notes if needed
- leave a clear next-session start point
- avoid bottom-of-file roadmap sprawl

Goal:
- finish the week with a roadmap that matches the real code state

---

## Good candidate side tasks when sessions finish early

These can still be inserted without derailing the main plan:

- update `TECHNICAL_DEEP_DIVE.md`
- update `README.md`
- tighten `VISION.md`
- improve minor UI text
- improve card hierarchy / layout clarity
- add screenshots / demo assets
- improve GitHub presentation
- refine LinkedIn / project positioning
- review Arbitrum direction later if relevant

---

## What success looks like now

In the immediate next stretch, success means:

- the product clearly shows **more than one real comparison universe**
- the visible UI wording feels understandable to normal users
- Raydium remains stable as a first non-Jupiter lane
- Meteora is either clearly feasible or clearly deferred
- the benchmark layer remains stronger and more honest than before
- the cost model keeps moving toward explicit-cost truthfulness
- the roadmap reflects the real current state instead of older pre-Raydium assumptions

---

## Next major milestone

**A credible Swap Transparency V1.5 foundation** where a user can:

1. connect Phantom  
2. choose a swap pair and amount  
3. see a strong benchmark/reference layer  
4. request executable quotes  
5. compare:
   - a Recommended route
   - a Direct route
   - a real non-Jupiter alternative
   - later a stable comparison anchor  
6. understand benchmark gap vs route-card cost logic  
7. trust that the app is being honest about what it knows and what it does not know  
8. feel that the product is becoming a true execution-comparison engine, not just a prettier single-router wrapper

---

## Resume point

**Start next session from card wording / surface-label cleanup now that Jupiter + Raydium comparison is live locally.**

Primary next goal:
- make the visible card language more user-facing and execution-surface-oriented

Example direction:
- **Via Jupiter**
- **Via Raydium**

instead of relying mainly on internal route/provider names.

### Fallback if wording cleanup finishes early
- continue with Meteora feasibility research

### Current locked order
1. Jupiter
2. Raydium
3. Meteora
4. Phantom later as comparison anchor

## Monday checkpoint — Jupiter/Raydium comparison surface upgraded

Today the swap comparison surface moved significantly closer to the intended multi-universe product model.

### Shipped locally
- visible route-card wording now prioritizes execution surfaces:
  - Via Jupiter
  - Via Raydium
- internal route labels such as BisonFi / HumidiFi / Scorch are no longer the main visible route wording
- backend ranking now supports normalized universe comparison across Jupiter and Raydium
- added `best_quote_option` and `recommended_option` separation:
  - best quote can come from any normalized universe
  - recommended executable route remains honest and executable-capable
- Raydium can participate in quote comparison while remaining:
  - quote-only
  - comparison-only
  - non-clickable
- default Alternatives now prioritize distinct universes instead of duplicate Jupiter internal variants
- Alternatives are no longer nested inside the Recommended card
- UI now renders:
  1. Recommended
  2. Direct route check
  3. Alternatives
- Raydium appears as the first non-Jupiter alternative when its quote succeeds
- Jupiter internal variants remain available in debug/details instead of crowding the default Alternatives section

### Product meaning
The app now communicates the intended model more clearly:

- Recommended = strongest current executable route
- Direct = special simpler route lens
- Alternatives = real non-Jupiter comparison universes

This makes Web3 Digest feel much closer to an honest execution-comparison product rather than a prettier Jupiter-only wrapper.

---

## Meteora decision — planned as next mini-sprint

Meteora is feasible, but it should be implemented carefully.

### Research conclusion
Meteora should not be added by relabeling Jupiter routes.

The honest first scope should be:

- Meteora DLMM only
- quote-only
- comparison-only
- non-clickable
- native Meteora pool quote path

### Why this is not a quick patch
Unlike Raydium, Meteora does not appear to expose the same simple mint-to-mint HTTP Trade API.

A proper first version likely requires:
- a small Node/JavaScript helper using Meteora DLMM SDK
- Python FastAPI calling that helper via subprocess
- pool discovery or configured pool candidates
- quote normalization into the existing option/card model
- failure/timeout handling
- tests

### Next-session resume point
Start next session from:

**Meteora DLMM quote-only integration plan.**

First implementation target:
- add a small Meteora DLMM quote helper path
- keep it disabled/fail-soft unless dependencies are available
- normalize successful quotes into:
  - provider = meteora-dlmm
  - execution_surface_label = Meteora
  - route_label = Meteora DLMM
  - is_comparison_only = true
  - is_clickable = false
- plug it into the existing universe-ranking flow beside Jupiter and Raydium

### Current universe order
1. Jupiter — executable / main aggregator universe
2. Raydium — quote-only comparison universe live locally
3. Meteora DLMM — next planned quote-only comparison universe
4. Phantom — later comparison anchor