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

So the real next step is:

### Tighten and harden the existing swap surface

That means focusing on:
- config hygiene
- wording polish
- cost explanation polish
- route comparison polish
- execution readiness groundwork

---

## Immediate next priorities

## Priority 1 — move swap infra secrets/config out of the frontend
The current swap fee-estimation flow works, but part of the implementation is still too exposed / temporary.

### Immediate task
- remove the hardcoded mainnet Helius RPC URL from the frontend
- move mainnet RPC configuration to backend/env-managed config
- keep the UI from directly containing sensitive or production-style infra values

### Why this matters
The feature works, but this is the first obvious hardening task before calling the surface stronger.

---

## Priority 2 — confirm and stabilize Jupiter auth/config usage
Even though the quote and instruction paths are already implemented, we should explicitly stabilize the configuration path.

### Immediate task
- confirm `JUP_API_KEY` is loaded cleanly in the active runtime
- confirm both `/swap/quote` and `/swap/instructions` are using the intended authenticated path
- confirm failure behavior stays clean when the key is missing or invalid
- avoid roadmap confusion by locking the real environment status

### Why this matters
The code path exists, but environment truth should be clean and explicit.

---

## Priority 3 — polish swap cost visibility
The current surface is already useful, but it should become tighter and easier to understand.

### Focus
- keep “Estimated trade execution cost” honest and simple
- keep route price impact separate from the reference gap
- continue showing network fee separately
- continue showing explicit route fees separately when available
- improve wording wherever the UI still feels too mechanical

### Why this matters
The product value is not only “get quote.”  
It is “help the user understand execution.”

---

## Priority 4 — improve the comparison UX
The ranking structure is already there, so the next job is presentation quality.

### Focus
- make the recommendation block more immediately understandable
- keep alternatives compact but meaningful
- keep direct-route lens useful without overclaiming
- reduce noise where the UI still feels debug-heavy
- keep inspection depth available behind expandable sections

---

## Immediate resume sequence for next session

Start next session with this exact sequence:

1. confirm current env truth:
   - `JUP_API_KEY`
   - mainnet RPC source
   - whether Helius is staying temporary or becoming the chosen default
2. move swap mainnet RPC usage out of frontend hardcode
3. retest Preview Quote
4. retest swap network-fee estimation
5. verify current wording for:
   - reference baseline
   - execution gap
   - route fees
   - network fee
6. decide whether the next build step is:
   - swap surface polish
   - swap execution groundwork
   - two-panel input evolution

This is the real clean start point.

---

## Near-term roadmap

## Phase A — Swap transparency V1 hardening
Goal: take the already-working quote surface and make it safer, cleaner, and more stable.

### Tasks
- move mainnet RPC config out of frontend hardcode
- clean env/config handling for swap infrastructure
- verify Jupiter auth path behavior cleanly
- keep quote preview stable
- keep swap instruction path stable
- keep network-fee estimation stable
- tighten failure messaging for infra/auth problems

### Outcome
The app keeps its current capabilities, but the foundation becomes more production-minded.

---

## Phase B — Swap transparency V1 polish
Goal: make the current surface feel more like a product and less like a debug workbench.

### Tasks
- tighten recommendation wording
- tighten comparison summary wording
- keep direct route framed as a lens, not a guaranteed winner
- reduce repeated text where the route cards feel noisy
- improve the hierarchy of what matters most:
  - spend
  - receive
  - execution gap vs reference
  - network fee
  - route complexity
  - protection settings

### Outcome
A clearer, stronger, more user-friendly comparison surface.

---

## Phase C — Cost explanation V1 polish
Goal: keep the cost story simple, honest, and easy to trust.

### Tasks
- keep the headline metric simple
- preserve explicit accounting scope
- avoid pretending to know fee components we do not actually know
- show explicit route fees only when truly available
- keep network fee separate
- possibly improve wording around “Execution gap vs reference”

### Outcome
A cleaner trust layer around the quote surface.

---

## Phase D — Two-panel swap input direction
Goal: move from the current one-line baseline area toward a stronger swap UX shape.

### Tasks
- evolve the input area toward a two-panel layout
- source side = user types amount
- destination side = live theoretical converted amount
- preserve fast inline reference behavior
- keep real executable quote request as a separate action

### Outcome
A more intuitive and more product-like swap entry experience.

---

## Phase E — Swap execution groundwork
Goal: prepare the app to move from quote intelligence toward controlled execution support.

### Tasks
- clarify boundary between quote path and execution path
- decide what execution step belongs next:
  - instruction handling
  - transaction assembly
  - wallet handoff
  - execution preview UX
- keep product philosophy intact:
  - compare first
  - explain clearly
  - execute later with trust

### Outcome
A cleaner path from quote intelligence into actual swap flow.

---

## Phase F — Provider / route expansion
Goal: move beyond a single comparison universe over time.

### Tasks
- keep Jupiter as the first ranking universe
- later add additional direct/provider paths
- compare across more route families and venue types
- eventually test whether independent direct integrations strengthen the comparison honestly

Possible later directions:
- Raydium direct
- Orca direct
- Meteora
- other route universes where technically feasible

### Outcome
A stronger execution-comparison layer, not just a Jupiter-first surface forever.

---

## Support-mode roadmap

## 1) Stronger diagnostics
Keep improving support-style visibility and trust.

### Tasks
- improve auth/config failure messages
- improve quote failure translations
- improve execution-related explanations
- keep route reasoning understandable
- keep debug depth available without overwhelming the default UI

## 2) Transaction explanation quality
The send flow already taught us that error translation matters.

### Tasks
- keep improving transaction-failure language
- preserve support-style product thinking
- reuse this mindset later in swap execution flows

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
After the current swap surface is stronger:

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

## Product decisions already locked

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
- config/auth truth is clean and explicit
- mainnet RPC handling is safer
- fee visibility is clearer
- comparison UX is easier to understand
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

That is the milestone we are driving toward now.