# Roadmap (Weekly / Monthly)

This file is the “where we’re going next” plan.
Updated weekly on Friday.

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

## What is effectively shipped so far

### Core app foundation
- FastAPI backend
- browser UI at `/ui`
- wallet-connected flow
- Phantom connect/sign boundary
- activity log
- transaction state handling
- route/quote UI foundation
- swap comparison surface
- debug visibility where needed

### Send / wallet-connected foundation
- Send SOL devnet path
- preflight insufficient-balance checks
- live devnet wallet balance display
- in-app devnet airdrop helper / diagnostics
- support-mode error translation

### Swap-transparency foundation
- swap quote surface inside `/ui`
- recommended route block
- alternative route block
- direct-route comparison block
- theoretical no-fee baseline
- route shortfall vs ideal display
- “Why this route?” product explanation
- softer product-facing note for Jupiter free-tier limitations
- reusable baseline helper on backend
- `/swap/inline-baseline` endpoint
- live ideal baseline behavior separated from executable quote preview

---

## Honest current status

### What is now real
- the app can connect Phantom
- the app can show a swap comparison surface
- the app can separate:
  - ideal/theoretical baseline
  - executable route comparison
- the app can explain recommendation logic in a user-facing way
- the app already has the skeleton of an execution-intelligence product

### What is not yet complete
- swap cost accounting is not fully computed yet
- route comparison is still Jupiter-first, not multi-universe yet
- the final swap input UX is not yet in its intended two-panel form
- the connected dashboard / holdings experience is still secondary and underdeveloped
- mobile-native execution is not a first-build priority yet

---

## Product identity (locked direction)

Web3 Digest is **not** trying to replace Phantom.

It is a **wallet-connected execution-transparency app**.

### Phantom handles:
- wallet creation
- custody / key management
- transaction signing
- trusted wallet security

### Web3 Digest handles:
- route comparison
- execution transparency
- ideal vs executable reference
- cost and shortfall visibility
- direct-route lens
- later, a better connected dashboard / holdings experience

This is a product built **on top of Phantom**, not **against Phantom**.

---

## Core product focus

### Immediate focus: swap transparency
We should focus **110% on swap transparency**.

That means the main product surface is:

- source token
- destination token
- typed amount
- ideal/theoretical baseline
- executable quote preview
- recommended route
- alternatives
- direct-route comparison
- route explanation
- honest limitations / data notes

### Secondary later focus: connected dashboard
Later, we can expand the connected wallet experience with:

- holdings view
- better token presentation
- charts / richer asset inspection
- activity/history
- improved portfolio visibility compared to the minimal wallet-number view

But this is a **later supporting layer**, not the main wedge right now.

---

## Product design direction

### Current state
The current inline baseline row is a **transitional UI**.

It works for now because it proves the behavior and keeps the architecture clean.

### Final direction
The swap input should evolve toward a more **stacked, two-panel, LlamaSwap-like layout**:

- **top panel**
  - source token
  - editable amount
  - supporting reference line

- **bottom panel**
  - destination token
  - live ideal/theoretical converted amount
  - supporting reference line

### Important design rule
The product should stay split into 2 layers:

#### Layer 1 — input / reference experience
- choose tokens
- type amount
- see live ideal conversion

#### Layer 2 — execution intelligence
- Preview Quote
- recommended route
- alternatives
- direct-route check
- later cost breakdown and venue-level transparency

This separation is now a core product rule.

---

## Routing roadmap direction

### Current routing layer
- Jupiter-first
- good enough to build the first real comparison surface
- good enough to validate product behavior and UX

### Future routing direction
To be truly credible as a transparency product, we cannot stop at Jupiter.

The roadmap should later integrate **at least two more routing / liquidity universes/providers** so route comparison becomes:

- richer
- more honest
- less dependent on one provider worldview
- more aligned with the product promise

This is now a strategic requirement, not just a nice-to-have.

---

## Platform direction

### Build path
- **web app first**
- mobile-aware product strategy
- native mobile not the first build

### Why web first
- fastest iteration
- easiest demo and showcase
- easiest GitHub packaging
- best for current product validation

### Why mobile awareness still matters
Real-world crypto swapping — especially in fast-moving meme/token environments — is often heavily **phone-first**, and Phantom’s strongest real-world advantage is its mobile habit and UI polish.

So even while staying web-first, the long-term product direction must remain:

- responsive
- mobile-aware
- able to translate well to phone usage patterns later

---

## This week — what we effectively shipped

### High level
- clarified product identity away from “new wallet”
- locked the wallet-connected execution-transparency direction
- clarified that Phantom remains the wallet/signing layer
- stabilized swap quote preview surface
- added live ideal baseline architecture
- split baseline/reference logic from executable quote logic
- improved user-facing wording:
  - Why this route
  - Route shortfall vs ideal
  - softer Jupiter-tier note
  - cleaner direct-route comparison note
- confirmed the product now has a real swap-transparency skeleton

---

## Open items right now

These are active product/roadmap items, not emergencies:

### Swap surface
- continue refining the baseline + quote UX
- evolve toward the two-panel swap input design
- later add fuller cost accounting
- continue improving explanation clarity

### Routing expansion
- plan the first non-Jupiter comparison additions
- keep swap integrations modular enough to support multiple providers later

### Connected dashboard
- decide how far to extend holdings/dashboard experience without turning into a wallet competitor
- improve token/portfolio presentation later

### Docs / packaging
- update docs so the product is framed correctly
- keep GitHub aligned with the new identity
- keep screenshots and README story current

---

## Near-term roadmap (next product stretch)

## Phase A — strengthen the swap-transparency core
**Goal:** make the swap surface feel like a real product, not just a prototype.

### Priorities
- keep live ideal baseline behavior stable
- keep Preview Quote reserved for executable routes only
- improve route explanation and comparison clarity
- improve direct-route lens presentation
- later add clearer cost breakdown structure
- make sure the product remains honest about limitations

### Definition of success
A user can connect Phantom, enter a swap, and clearly understand:
- the ideal reference
- the recommended executable option
- meaningful alternatives
- whether a direct route exists
- why the recommendation was chosen

---

## Phase B — move toward final swap input UX
**Goal:** evolve the UI shape without losing the engine/behavior separation.

### Priorities
- move from one-line baseline row to a two-panel swap input
- keep ideal reference inside the token input experience
- preserve execution intelligence below that layer
- improve clarity without rushing “pretty UI” too early

### Definition of success
The swap input starts to feel closer to a real production interaction model while still sitting on the same clean backend/reference architecture.

---

## Phase C — connected dashboard / holdings expansion
**Goal:** improve the wallet-connected portfolio experience without becoming a wallet competitor.

### Priorities
- token holdings view
- improved presentation of balances
- later charting / richer portfolio visibility
- better asset inspection than a plain symbol-and-number display

### Definition of success
A connected Phantom user gets a clearer and more useful holdings/dashboard experience than the default minimal wallet view.

---

## Phase D — multi-provider route transparency
**Goal:** make the product’s transparency promise more credible.

### Priorities
- integrate at least two more routing/liquidity universes/providers
- compare beyond Jupiter-only
- improve route ranking and transparency logic
- make “best route” claims more robust

### Definition of success
The product can compare more than one provider worldview and give users a stronger reason to trust the surface.

---

## Strategic themes

### 1) Build on Phantom, do not compete with it
Phantom is the wallet.
Web3 Digest is the intelligence layer.

### 2) Swap transparency is the wedge
This remains the strongest and clearest product focus.

### 3) Ideal reference and executable route must stay separate
This is central to both architecture and UX.

### 4) Direct route should remain a distinct comparison lens
It is not automatically better, but it is often simpler, easier to inspect, and useful as a trust-building comparison.

### 5) Web first, mobile-aware
The product should validate on the web first, but never lose sight of the fact that much real swapping behavior is mobile-first.

---

## Risks / constraints to remember
- public RPC limits are real
- provider limitations / pricing tiers affect comparison coverage
- giant inline UI structures are fragile unless continuously cleaned
- route comparison becomes much stronger only once we expand beyond Jupiter
- connected dashboard scope must stay disciplined so we do not drift into “build another wallet”

---

## What success looks like in the next stage

The product should increasingly feel like this:

> “I connect Phantom here not because I need another wallet, but because this app helps me understand my swap better than my wallet does.”

That is the real bridge from prototype to product.