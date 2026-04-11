# Roadmap (Weekly / Monthly)

This file is the “where we’re going next” plan.  
Updated weekly on Friday.

---

## Current phase

**Swap-transparency V1 is now the clear product wedge.**

We are no longer primarily building “a wallet that can also do swaps.”  
We are building a **wallet-connected execution-transparency app**.

That means:

- Phantom remains the wallet, signer, and security layer
- Web3 Digest becomes the place where users:
  - connect their wallet
  - compare swap routes
  - understand costs and tradeoffs
  - make better execution decisions
  - later view holdings and portfolio data in a clearer connected dashboard

The product direction is now much more precise:

**connect Phantom, swap with transparency, then expand the connected dashboard experience later.**

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
Compare multiple execution shapes and venue-restricted routes first, then expand into independent routers, direct venue integrations, and multichain execution intelligence.

### Moat
We make execution understandable, trustworthy, and cost-transparent — and we let users compare meaningful alternatives instead of executing blindly.

### North star
**Make swaps feel free:** no hidden wallet tax, radically transparent costs, and execution that minimizes total user cost as much as possible.

### One-line pitch
**Web3 Digest helps users compare swap routes, understand costs, and choose the best execution with no hidden wallet-layer markup.**

---

## What is active right now

The swap product wedge is already live.

So the roadmap should now start from:

- refining the existing quote/comparison surface
- hardening the implementation
- improving the product wording and trust layer
- preparing the first clean Swap Transparency V1 demo

This is important:

**the main next step is no longer “get JUP key and unlock the quote path.”**  
That path is already materially working.

---

## True current resume point

The current app state already includes:

- authenticated-capable Jupiter quote path
- authenticated-capable Jupiter swap-instructions path
- live quote preview UI
- inline baseline updates while typing
- network-fee estimation in the UI
- recommended + alternatives + direct-route comparison structure
- recommended-route cost summary in USD
- nested alternatives under the recommended card
- a lighter direct-route comparison card
- a cleaner, more mobile-friendly quote hierarchy

So the real next step is:

### Tighten, polish, and prepare the swap surface for actionability

That means focusing on:
- wording polish
- cost explanation polish
- route comparison polish
- interaction-model decisions
- execution readiness groundwork

---

## Core product principle for the next stretch

**We are optimizing for a trustworthy, executable swap-intelligence surface first.**  
Final visual polish, warmer branding, richer design language, and broader dashboard polish come later, after the interaction model and execution flow feel strong.

That means:

- engine quality first
- clear UX skeleton second
- pretty UI later

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

## Immediate next priorities

## Priority 1 — finish swap-surface polish
The main comparison surface is now structurally much stronger, but it still needs final tightening.

### Focus
- keep the Recommended card as the main answer
- keep Alternatives nested under Recommended
- keep Direct as the lighter second card
- improve spacing and readability
- reduce any remaining repeated or overly mechanical wording
- keep the surface compact and mobile-friendly

### Why this matters
The quote surface is now the product.  
This is no longer just UI cleanup — it is product-shaping work.

---

## Priority 2 — lock the interaction model
The structure is now strong enough that we should explicitly define how users interact with it.

### Focus
- define what expands
- define what executes
- keep expand and execute as separate behaviors
- define future CTA strategy
- preserve mobile-safe interaction logic

### Why this matters
This is the bridge from:
- compare
- understand
- choose
- execute

If we skip this and jump into execution, the surface may become messy fast.

---

## Priority 3 — prepare Recommended route actionability
The recommended route should become actionable first once the interaction model is locked.

### Focus
- selected-route state
- execution-prep flow
- Phantom-connected handoff thinking
- loading / confirm / fail states
- trust-preserving action flow

### Why this matters
Recommended is the main product answer and should be the first route that becomes executable.

---

## Priority 4 — keep benchmark and cost quality honest
The current cost model is useful and already live, but it still needs to stay under active observation.

### Focus
- watch execution-cost behavior, especially frequent zero-cost outcomes
- continue using CoinGecko as the current benchmark source
- later support DexScreener for long-tail / meme tokens
- keep route fees honest
- keep network cost honest
- preserve strict scope clarity

### Why this matters
The UI can only be as trustworthy as the benchmark logic behind it.

---

## Locked product decisions already active

These should remain stable unless intentionally changed later.

### Identity
Web3 Digest is a **wallet-connected execution-transparency app**, not a Phantom replacement wallet.

### Core value
Help users compare routes, understand costs, and make better execution decisions.

### Trust philosophy
We do not invent precision.  
We do not hide the cost story.  
We do not claim superiority without declared scope.

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

## Locked UX decision — swap cost transparency layer

### Why this matters
A core part of the product mission is not just to show a quote, but to explain **what the swap costs** in a way that is simple, transparent, and economically meaningful.

The product should help the user answer:

**“What is this swap going to cost me, and why?”**

That means the swap surface should not just show route names and output amounts. It should make the cost structure understandable.

This UX decision sharpens the product identity:

- Web3 Digest should show a clear **estimated total swap cost**
- that headline number should be backed by a transparent breakdown
- the breakdown should separate:
  - execution cost
  - network cost
  - route fees
- the user should be able to inspect the breakdown without cluttering the default view

This fits the mission because the product is meant to make swaps:
- more understandable
- more trustworthy
- more cost-transparent

Not just “quote-first,” but **cost-explained**.

---

### What this decision impacts
This decision affects:

- the core swap-card UX
- the naming of cost fields
- the backend cost model
- how we define and calculate the product’s main user-facing metric
- how we explain known vs unknown cost components
- how we compare routes later

It also sets up future route ranking logic, because eventually the product should compare routes using a user-facing cost lens rather than only raw output.

---

### Locked wording and visual structure

#### Main headline in recommended route card
**Estimated total swap cost: $X.XX**

This is the main cost number the user sees first.

#### Breakdown behind expandable details
- **Execution cost:** $X.XX
- **Network cost:** $Y.YYYY
- **Route fees:** $Z.ZZ

If route fees are not disclosed, the breakdown should show:

- **Route fees:** not disclosed for this swap

#### Headline math rule
The headline must equal the sum of all **known numeric components only**.

So:

- if route fees are disclosed:
  - **Estimated total swap cost = execution cost + network cost + route fees**
- if route fees are not disclosed:
  - **Estimated total swap cost = execution cost + network cost**
  - and the breakdown must say:
    - **Route fees: not disclosed for this swap**

We are intentionally not adding extra warning text into the headline area for this case. The word **Estimated** plus the breakdown is enough.

---

### Meaning of each cost line

#### Execution cost
This is the economic shortfall between the executable quoted route and the fresh theoretical reference baseline.

User-facing meaning:
- how much worse the executable swap is than the fresh reference market baseline

This should be shown in **USD**.

#### Network cost
This is the estimated blockchain transaction cost for the swap transaction.

User-facing meaning:
- the estimated on-chain transaction cost required to perform the swap

This should be shown in **USD** in the UI, even if internally it is computed in lamports / SOL first.

#### Route fees
These are fees explicitly disclosed by the route / quote response.

User-facing meaning:
- fees disclosed by the swap path itself

If the quote does not disclose them clearly, the UI should say:

- **Route fees: not disclosed for this swap**

We do not fabricate or guess a numeric route-fee amount if it is not disclosed.

---

### Immediate UX direction
For the recommended route card:

#### Default visible
- route recommendation
- receive amount
- protections
- **Estimated total swap cost: $X.XX**

#### On expand
Show the breakdown:
- **Execution cost:** $...
- **Network cost:** $...
- **Route fees:** $... or *not disclosed for this swap*

This keeps the default surface simple while preserving transparency.

---

### Implementation rules already adopted
Backend should return clearly separated fields for the recommended route:

- `execution_cost_usd`
- `network_cost_usd`
- `route_fees_usd` or `null`
- `route_fees_disclosed` boolean
- `estimated_total_swap_cost_usd`

Rules:
- `estimated_total_swap_cost_usd` must equal the sum of the known numeric components only
- if route fees are not disclosed, they are excluded from the numeric total
- the UI headline should use USD

---

## Locked UX checkpoint — transparency line vs total swap cost

### Decision
We are keeping a **two-layer explanation model** in the swap surface:

#### 1. Top transparency line
This remains separate from the cost card and explains the executable quote against the fresh market reference.

Current wording can evolve later, but the concept is locked as:

- **Executable output vs reference: -0.396547 USDC (-0.048348%)**

This line tells the user:

- how far the real executable route is from the theoretical reference conversion
- how much output is lost (or gained) relative to the fresh benchmark
- that the benchmark comes from a live market reference source (currently CoinGecko, later possibly DexScreener for tokens not covered there)

This is a **transparency metric**, not the total user-cost headline.

---

#### 2. Cost card headline
This is the separate user-facing cost summary:

- **Estimated total swap cost: $X.XX**

This headline tells the user the known all-in cost currently included in the model:

- execution cost
- plus network cost
- plus disclosed route fees when available

This is the **cost metric**, not the benchmark-comparison line.

---

### Why this separation is correct
We are explicitly **not** collapsing these into one line.

That is because they answer two different questions:

#### Transparency question
**“How does the executable quote compare to the fresh market reference?”**

Answered by:
- **Executable output vs reference**

#### Cost question
**“What is the known estimated cost of doing this swap?”**

Answered by:
- **Estimated total swap cost**

This separation is good product design because it preserves both:
- route-quality transparency
- practical cost understanding

without forcing one metric to do both jobs.

---

### Locked meaning of each line

#### Executable output vs reference
This is the output delta between:
- the fresh theoretical reference conversion
- and the recommended executable route output

It is currently expressed in output-token terms and percent.

This line is mathematically correct as an **execution/reference delta**.

It is **not** the full total swap cost.

#### Estimated total swap cost
This is the known-cost estimate currently modeled for the recommended route.

Formula:

- **Estimated total swap cost = execution cost + network cost + disclosed route fees**

If route fees are not disclosed:
- they are not invented
- they are not added numerically
- the breakdown should say:
  - **Route fees: not disclosed for this swap**

So the headline remains the sum of the **known numeric components only**.

---

### Locked product rule
We keep these two ideas distinct:

- **Executable output vs reference** = transparency metric
- **Estimated total swap cost** = known all-in cost metric

We should not replace one with the other.

Both stay in the product.

---

### Current visual direction
#### Top reference/transparency area
Keep:
- **You spend: ...**
- **CoinGecko reference: ...**
- **Executable output vs reference: ...**
- **Source: ...**

This remains above the recommended card.

#### Recommended cost card
Show:
- **Estimated total swap cost: $X.XX**
- expandable breakdown:
  - **Execution cost: $...**
  - **Network cost: $...**
  - **Route fees: $...** or `not disclosed for this swap`

This is the cost layer.

---

### Future wording note
The exact wording of the top transparency line may be improved later.

Possible future direction:
- make the line sound more product-clean
- possibly rename it toward something like:
  - reference conversion
  - executable quote vs reference
  - real swap quote vs reference conversion

But the **conceptual separation is now locked**, even if the wording evolves.

---

## Locked UI structure checkpoint — 2-card quote surface with nested alternatives

### Decision
We are simplifying the Preview Quote surface into a **mobile-first 2-card hierarchy**.

The main swap result area should not be split into 3 equally heavy sections anymore.

Instead, the structure is now locked as:

- **2 main cards**
- **alternatives nested under recommended**
- **compact expandable alternatives**
- **mobile-first hierarchy**

---

### Main card structure

#### Card 1 — Recommended
This is the primary answer for the user.

It should contain:
- route / provider
- receive amount
- protections
- **Estimated total swap cost**
- expandable cost breakdown
- nested expandable **Alternatives** subsection

#### Card 2 — Direct / simpler route
This is the secondary comparison card.

It should contain:
- simpler-route framing
- receive amount
- route shape / step count
- execution comparison
- lighter explanation than the recommended card

This card should help the user compare:
- best route
- simpler route

without overwhelming the screen.

---

### Alternatives move under Recommended
We are no longer treating Alternatives as a full third always-open section.

Instead:

- Alternatives should live **inside the Recommended card**
- they should appear under a small expandable subsection such as:
  - **Alternatives**
- when expanded, they should show compact alternative rows/cards

This keeps alternatives available without letting them compete visually with the main recommendation.

---

### Compact alternative design
Alternatives should be shown in a much lighter format than the full main cards.

For each alternative, show only the essentials:

- alternative label / route name
- receive amount
- execution cost
- shape or step count

Example structure:

- **Alternative 1 — TesseraV**
  - Receive: `819.0722 USDC`
  - Execution cost: `$1.01`
  - Shape: `single-path`

- **Alternative 2 — Scorch**
  - Receive: `819.0422 USDC`
  - Execution cost: `$1.04`
  - Shape: `2-step path`

Do **not** show the full verbose fee/network/explanation block by default inside alternatives.

Those details can be expanded later if needed.

---

### Why this change is important
This makes the product:

- more compact
- easier to scan
- more mobile-friendly
- closer to the real use case of swap-heavy mobile behavior
- clearer in hierarchy

The user should first understand:

1. what we recommend
2. what the simpler direct route is
3. what the other options are only if they choose to inspect them

That is a better product surface than forcing all 3 sections open at once.

---

### Mobile-first rule
This UI decision supports the long-term north star that the product should be easily adaptable into a mobile app.

That means:
- vertical stacking
- tap-to-expand sections
- short visible summaries
- reduced repeated text
- fewer always-open blocks

This quote surface should remain easy to map into a phone screen later.

---

## Locked interaction model checkpoint

### Button vs whole-card tap
CTA should be a **button**, not whole-card click.

Reason:
- safer for mobile
- reduces accidental taps
- cleaner once cards contain expandable sections

### Expand vs execute
These remain separate behaviors.

- **Expand** = reveal more information
- **Execute** = start the swap flow

We should not overload the same tap target with both behaviors.

### Alternatives interaction rule
Alternatives should:
- expand via tap, not hover
- remain informative only for now
- not be executable yet
- become inspect-first later

That means:
- user expands Alternatives
- sees compact rows
- rows remain non-clickable for now

### Execution sequencing
The current intended actionability order is:

1. **Recommended becomes actionable first**
2. **Direct becomes actionable second**
3. **Alternatives become richer/selectable later**

This keeps the main answer and the main comparison lane prioritized.

---

## Locked CTA wording checkpoint

### Recommended CTA
**Swap this route**

This should be the first primary actionable button in the product.

### Direct CTA
**Try direct route**

This keeps the comparison tone and makes the user deliberately choose the simpler path.

### Alternatives
No executable CTA yet.

Later options may include:
- **View route details**
- **Choose this option**

But this is not locked yet because alternatives are still informative-only.

---

## Provisional CTA placement checkpoint

For the current desktop/web phase:

- CTA button should sit in the **lower-right area of the card**
- not flush to the far edge
- not hidden inside expanded details
- visible enough to feel actionable
- compact enough to avoid making the card too vertically long

This is a provisional placement rule, not final visual design.

For mobile, exact placement can be revisited later.

---

## Backend / engine garage — parked items for later return

### Current checkpoint
For the current sprint phase, the backend/engine side is in a **good enough state** to support UI/product work.

We have already reached a solid checkpoint with:

- backend-owned quote flow
- backend-owned fee logic for the recommended route
- fallback fee behavior when RPC fee method is unavailable
- recommended-route cost summary in USD
- honest handling of undisclosed route fees
- separation between:
  - transparency metric
  - total swap cost metric

This means the frontend/UI can now continue without being blocked by missing backend structure.

---

### Why backend work is being paused for a few sessions
We are intentionally shifting focus to the swap surface UX because the next highest-value work is now:

- hierarchy
- compactness
- mobile-first layout
- recommended vs direct card structure
- nested alternatives
- cleaner wording and user understanding
- interaction model lock

The backend is **not finished forever**, but it is **sufficient for this phase**.

---

### Backend / engine items still parked for later

#### 1. Better network fee estimation
Current state:
- recommended route network fee uses a fallback estimate when the Solana RPC fee method is unavailable

Later improvement:
- move beyond the current generic fallback
- get closer to transaction-specific estimation
- possibly use a more realistic built-transaction or simulation-aware path later

Goal:
- improve confidence in the network-cost line
- reduce dependence on generic fallback logic

---

#### 2. Better route-fee state model
Current state:
- route fees are shown only when explicitly disclosed and priceable
- otherwise they fall back to:
  - `not disclosed for this swap`

Later improvement:
- distinguish more clearly between:
  - disclosed and priceable
  - disclosed but not priceable
  - not disclosed

Goal:
- improve truthfulness and UX clarity
- avoid lumping all non-numeric fee cases into the same bucket forever

---

#### 3. Stronger cost-summary coverage beyond recommended route
Current state:
- the rich cost-summary model is mainly attached to the recommended route

Later improvement:
- decide whether and when to add richer cost summaries for:
  - direct route
  - alternatives
- keep rate-limit pressure and provider load in mind

Goal:
- extend cost intelligence carefully without bloating the preview flow

---

#### 4. Better handling of complex / long-tail token references
Current state:
- top transparency/reference layer currently depends on CoinGecko for fresh reference pricing

Later improvement:
- support DexScreener or similar for long-tail tokens / memes not reliably covered by CoinGecko
- especially important for future routes like meme token -> meme token paths

Goal:
- preserve the transparency/reference layer even for more exotic swaps

---

#### 5. More exact product-grade execution / cost logic
Current state:
- execution cost is based on benchmark shortfall vs fresh reference
- network cost is added separately
- disclosed route fees are included only when available
- execution cost is floored at zero when the executable route beats the reference

Later improvement:
- continue refining the product-grade known-cost model
- keep the formula honest and transparent
- decide whether to later expose “beats reference” language in addition to zero-cost presentation

Goal:
- make sure the swap-cost model stays mathematically sound and easy to explain

---

#### 6. Future backend support for broader route comparison
Current state:
- current quote surface is still Jupiter-first

Later improvement:
- when the roadmap reaches broader comparison work, backend may need to support:
  - additional route/provider sources
  - direct venue comparisons
  - stronger comparison normalization

Goal:
- prepare for later execution-intelligence expansion without forcing it prematurely now

---

### Locked rule while paused
During the current UI sprint, backend work should only be resumed immediately if:

- the UI becomes blocked by missing backend data
- the current backend behavior becomes misleading or incorrect
- a major bug appears in quote/cost logic

Otherwise, keep backend work parked and focus on UI/product structure.

---

### Resume point when returning to the garage
When we decide to go back into backend/engine work, start by reviewing:

1. network fee estimation quality
2. route-fee state handling
3. recommended-route cost-summary accuracy
4. support for long-tail token reference pricing
5. whether direct/alternative routes need richer backend summaries
6. whether benchmark quality should be upgraded beyond CoinGecko-first behavior

This should be the starting checklist for the next backend-focused sprint.

---

## Two-panel swap input direction

This remains an important near-medium-term direction and should not be lost while working on card/actionability phases.

### Goal
Move from the current one-line baseline area toward a stronger swap UX shape.

### Tasks
- evolve the input area toward a two-panel layout
- source side = user types amount
- destination side = live theoretical converted amount
- preserve fast inline reference behavior
- keep real executable quote request as a separate action

### Outcome
A more intuitive and more product-like swap entry experience.

This is not the immediate next step, but it remains a real planned direction.

---

## Macro progression map

## Phase 1 — finish swap decision surface
Goal: make the quote surface feel like a real product.

### Focus
- alternatives subsection polish
- top summary line polish
- tiny-cost formatting
- wording cleanup
- mobile compactness
- clean visual hierarchy

### Status
In progress and close to a checkpoint.

---

## Phase 2 — lock the interaction model
Goal: define how users interact with cards before execution exists.

### Locked already
- CTA = button, not full card
- expand and execute are separate
- alternatives expand, not hover
- alternatives are informative only for now
- recommended gets executable first
- direct gets executable second

### Still to refine
- exact button placement in the cards
- exact CTA visibility rules
- what expands by default
- what remains hidden until tapped

---

## Phase 3 — make Recommended actionable
Goal: turn the Recommended card from informational into executable.

### Likely work
- add Recommended CTA button
- prepare route-selection state
- connect to Phantom flow
- execution handoff path
- execution loading / confirmation state
- failure/debug state

This is the first real bridge from compare → execute.

---

## Phase 4 — make Direct actionable
Goal: let the user deliberately choose the simpler route.

### Likely work
- add Direct CTA
- keep it clearly distinct from Recommended
- support separate execution path/handoff
- preserve comparison meaning

This is important because it shows the product is not blindly pushing only one route.

---

## Phase 5 — improve benchmark/reference quality
Goal: make the comparison engine stronger.

### Focus
- understand zero-cost frequency
- continue using CoinGecko for now
- later add DexScreener for long-tail / meme tokens
- better benchmark quality
- maybe later show “beats reference” when appropriate

This improves trust and makes the cost surface more meaningful.

---

## Phase 6 — support more pairs
Goal: expand beyond SOL/USDC.

### Focus
- more supported pairs
- long-tail assets
- meme pairs
- harder route shapes
- more realistic user scenarios

This is important, but should come after the surface and interaction model are stronger.

---

## Phase 7 — alternatives inspect layer
Goal: make alternatives richer without making them executable too early.

### Likely direction
- user expands Alternatives
- alternative rows remain informative first
- later user may tap a row to inspect that route in more detail
- only after that do we decide whether an alternative becomes directly selectable/executable

Not immediate priority, but clearly on the path.

---

## Phase 8 — visual / pretty UI phase
Goal: turn the structurally-correct surface into a visually strong product.

### Focus
- cleaner card system
- stronger spacing
- better visual hierarchy
- more LlamaSwap-like feel
- more app-like / mobile-native polish
- warmer branding / more welcoming product feel later

This should come on top of a structure we already trust.

---

## Connected dashboard roadmap

The connected dashboard remains important, but it is no longer the lead wedge.

### Next dashboard layers can include
- cleaner holdings view
- stronger portfolio presentation
- better history UX
- more polished connected identity
- later improvements to the “wallet cockpit” feel

But the main wedge remains:
**swap transparency first.**

---

## Medium-term roadmap

## 1) Receive / send expansion
After the current swap surface and actionability model are stronger:

Possible order:
- Receive UX
- Send SOL polish
- Send SPL token flow
- later execution handoff refinement

## 2) Better execution intelligence
After V1 comparison stabilizes:

- more route families
- better transparency layers
- stronger recommendation logic
- richer cost comparison

## 3) Multichain later
Stay Solana-first for now.

Later expansion can include:
- EVM connected dashboard slices
- Arbitrum-specific direction
- multichain quote/comparison logic
- eventually broader execution intelligence across chains

---

## This week checkpoint

### What was achieved
This week materially moved the quote surface from a heavier prototype toward a real product structure.

Key shifts:
- Recommended became the clear main card
- Alternatives moved under Recommended
- Direct became a lighter second card
- the top transparency layer stayed separate from the cost layer
- the cost story became clearer
- the UI became more mobile-friendly and less debug-heavy
- the backend garage was deliberately parked while the surface was shaped

This is a meaningful checkpoint.

---

## Next week plan (5-day build week)

### Day 1 — finish quote-surface polish
Focus:
- inspect the Alternatives subsection carefully
- tighten spacing and compactness
- confirm the top summary wording
- confirm tiny-cost formatting rule
- confirm the quote surface feels clean enough before actionability work begins

Goal:
- close the “quote surface polish” chapter cleanly

---

### Day 2 — lock actionability design
Focus:
- confirm CTA wording in the UI
- confirm CTA placement
- confirm what expands vs what executes
- confirm alternatives remain informative only
- confirm direct route is the second executable lane

Goal:
- fully lock the interaction model before coding execution

---

### Day 3 — start Recommended execution groundwork
Focus:
- make Recommended the first actionable route
- connect button flow to route selection / execution prep
- Phantom-connected handoff planning
- selected-route state
- beginning of compare → execute bridge

Goal:
- first real execution groundwork for the core route

---

### Day 4 — continue execution groundwork
Focus:
- recommended route execution state handling
- loading / confirm / fail / retry states
- support/debug visibility where needed
- begin Direct route actionability planning or first implementation step

Goal:
- make the action model realistic and supportable

---

### Day 5 — Direct route + sprint review
Focus:
- extend the action model toward Direct route
- review what works and what still feels weak
- decide what the following sprint should be:
  - continue execution work
  - improve benchmark engine
  - add more pairs
  - or begin prettier UI phase

Goal:
- end the week with a clear next-sprint branch

---

## Good candidate tasks when a session finishes early

These can be inserted without derailing the main roadmap:

- update `TECHNICAL_DEEP_DIVE.md`
- update `README.md`
- tighten `VISION.md`
- improve minor UI text
- improve card hierarchy / layout clarity
- add screenshots / demo assets
- improve GitHub presentation
- refine LinkedIn / project positioning
- plan route-expansion strategy
- review Arbitrum positioning later when relevant

---

## What success looks like in the next stretch

We should be able to say:

- the roadmap matches the real code state
- the swap surface is already live and stable
- the cost story is clear and trustworthy
- the interaction model is clean and intentional
- Recommended is ready to become actionable
- Direct is clearly positioned as the second route choice
- the app feels like a real execution-transparency product, not just an internal prototype

That is the immediate target.

---

## Next major milestone

**A credible Swap Transparency V1 demo** where a user can:

1. connect Phantom  
2. choose a swap pair and amount  
3. instantly see a theoretical reference baseline  
4. request executable quotes  
5. compare the recommended route, alternatives, and a direct-route lens  
6. understand the execution gap and fee story clearly  
7. trust that the app is being honest about what it knows and what it does not know  
8. see a clear path toward taking action on the recommended route

That is the milestone we are driving toward now.