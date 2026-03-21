# Web3 Digest — Vision (North Star)

## Product Identity
**Web3 Digest is an execution-intelligence layer for swaps, wrapped in a wallet-like experience.**

We are not trying to build just another wallet UI, just another swap button, or just another dashboard.  
We are building a product that helps users:

- compare
- understand
- choose
- execute

with clearer costs, more honest route visibility, and no hidden wallet-layer markup.

---

## One-Line Pitch
**Web3 Digest helps users compare swap routes, understand costs, and choose the best execution with no hidden wallet-layer markup.**

---

## Mission
**Help people make better swaps by making execution transparent, understandable, and low-cost.**

---

## Vision
**Build the most trusted, user-friendly swap experience in crypto — simple enough for non-crypto natives, transparent enough for power users.**

---

## Purpose
**Protect users from blind execution, hidden wallet-layer costs, and route opacity.**

---

## Direction
**Compare multiple execution shapes and venue-restricted routes first, then expand into independent routers, direct venue integrations, and multichain execution intelligence.**

This means:

- first, build a strong comparison surface using a coherent ranking system
- then, deepen that comparison with more route shapes and venue-restricted options
- later, add direct venue/provider integrations to make ranking more robust and more honest
- eventually, extend the same execution-intelligence model across chains

---

## Moat
**We make execution understandable, trustworthy, and cost-transparent — and we let users compare meaningful alternatives instead of executing blindly.**

Our moat is not “we also fetch a quote.”

Our moat is:

- cost transparency
- route transparency
- understandable tradeoffs
- meaningful choice
- honest diagnostics
- no hidden wallet-layer tax

Over time, this moat should deepen through:

- better comparison design
- stronger route/cost explanation
- more robust multi-provider ranking
- execution-quality data
- trust earned through honest UX

---

## North Star
**Make swaps feel free: no hidden wallet tax, radically transparent costs, and execution that minimizes total user cost as much as possible.**

Internal rallying cry:

**Fee-free swaps.**

That does not mean pretending swaps have zero cost.  
It means pushing toward:

- no extra wallet-layer markup
- lower effective total cost
- clearer cost visibility
- better default execution

---

## Product Thesis
Many wallet users accept bad swap UX because it is convenient:

- wallet UIs often hide route quality
- wallet in-app swaps can feel expensive
- small swaps get punished hardest by hidden markup, spread, or poor execution
- most users do not actually understand what the swap is costing them

**Web3 Digest aims to become the product that explains execution clearly, minimizes hidden overhead, and helps users choose with confidence instead of executing blindly.**

The long-term wedge is:

- better route transparency
- clearer total-cost visibility
- meaningful route comparison
- smart defaults for low-size swaps
- route and venue logic optimized for retail-small transactions
- execution through a connected wallet, not through custody by us

---

## Start Here: Solana First
The long-term vision remains **multichain**, but we should not start everywhere at once.

### Why Solana first
- we already have a Solana-based project foundation
- Phantom gives us a clean non-custodial signing boundary
- Solana is a strong environment for retail-sized swaps, memecoins, and price-sensitive activity
- the route/venue landscape is rich enough to build a real execution-intelligence UX

### Beachhead Thesis
We start by building the best **small-swap execution-intelligence UX on Solana**, then expand outward.

---

## Product Principles (Rules We Do Not Break)

### 1) No custody in V0 / V1 / early V2
We do not handle:

- seed phrases
- private keys
- custody of user funds

The user’s wallet signs. Our app compares, explains, and orchestrates.

### 2) Wallet = signer, not swap store
Phantom (or another connected wallet later) is the signing boundary.  
Our app should own:

- quote comparison
- route explanation
- execution framing
- cost visibility
- diagnostics
- support UX

The wallet should authorize, not define the swap product.

### 3) No hidden wallet markup
We cannot promise “zero total cost,” because swaps still have:

- network fees
- pool / venue fees
- slippage / spread
- execution tradeoffs

But our product goal is:

- **no hidden wallet-layer swap tax**
- **clear total-cost visibility**
- **better route selection**

### 4) Truthful metrics
If data is stale, missing, uncertain, or only partially available, we show that honestly.

No fake confidence perfume.

### 5) Snapshot-first architecture
History, caching, and snapshots come before API spam.  
This keeps the product truthful, inspectable, and scalable.

### 6) Start narrow, then expand
We begin with:

- Solana
- wallet connect
- balances / history
- send
- quote / compare
- then execute

Only after that do we push further into:

- SPL send
- richer swap execution
- multichain

### 7) Product clarity beats feature clutter
If a route is cheaper, the user should understand **why**.  
If a route is not recommended, the user should understand **why**.  
If a swap fails, the user should understand **why**.

### 8) Build additive layers, not rewrites
Each version should extend the product cleanly.

---

## Core UX Philosophy

### The product should show the economic result first
Users should understand, in the clearest way possible:

- what they spend
- what they receive
- what the swap is costing them
- what protects them
- why a route is being recommended

The UI should prioritize the **economic outcome**, not just token quantities.

### The product should separate four things clearly
#### Outcome
What the user gets back

#### Cost
What the swap is costing overall

#### Protection
What minimum outcome and slippage settings protect the user

#### Route
How the product is achieving the swap

This separation is one of the main product advantages.

---

## Swap Comparison Surface (Current Product Direction)

### Main Structure
The default swap comparison surface should have **2 blocks**:

#### Block 1 — Recommended route
The top route selected by the main ranking logic.

Inside this block there is a sub-block:

##### Other options
Two compact, expandable alternatives:
- **2nd best**
- **3rd best**

These are ranked by the **same main parameter** used to elect the recommended route.

This is the transparency block.

#### Block 2 — Direct route check
A separate comparison lens for users who want the **most direct / fewer-step route**, with its own cost breakdown and tradeoff explanation.

This is the route-shape transparency block.

### What the Recommended Route should show by default
- You spend
- You receive (estimated)
- Estimated total swap cost
- Protection
- Route path
- Why this route

### What the alternatives should show by default
Compact by default, expandable on click:

- label
- receive
- estimated total swap cost
- one-line reason

Expanded view can show:
- minimum received
- protection details
- path
- cost breakdown

### What the Direct Route Check should communicate
The direct-route block should be positioned as:

- fewer steps
- easier route shape to inspect
- potentially lower complexity
- **not necessarily the best total value**

It should avoid overpromising that “direct” always means “cheaper.”

---

## Cost Philosophy

### Headline metric
The main cost line should be:

**Estimated total swap cost**

### Reconciliation rule
The cost breakdown must add up **exactly** to the headline number.

If the UI says:

**Estimated total swap cost: $3.80**

then the displayed breakdown must sum to **$3.80** exactly.

### Cost breakdown labels (simple language)
For now, the breakdown should use simple labels:

- **Execution cost**
- **Network fee**
- **Extra wallet fee** *(only if it exists)*

Later, “Execution cost” can have a tooltip/hover explanation.

### Accounting principle
The chosen accounting scope must be explicit and consistent.

The long-term default should lean toward the **full user cost** of the action, not a selectively incomplete number.

---

## Product Shape

### Layer 1 — Portfolio & state
- balances
- price snapshots
- history
- deltas
- truthful stale/missing data handling

### Layer 2 — Route intelligence
Our app compares possible swap paths and tells the user:

- expected output
- total cost
- protections
- route path
- likely best choice
- runner-up options
- direct-route alternative

### Layer 3 — Execution
The user chooses a route.  
Our app prepares the transaction.  
The connected wallet signs.  
Execution happens on-chain through the chosen route / venue.

### Layer 4 — Support mode
The app explains:

- bad routes
- unsupported pairs
- stale data
- insufficient balance
- route not found
- provider / RPC errors
- swap failure reasons
- what the user should do next

---

## Version Ladder

### V0 — Read-only wallet (CLI-first) ✅
**Shipped / foundation:**
- Solana balances: SOL + SPL tokens
- SQLite snapshots for balances / prices / portfolio history
- portfolio report with truthful deltas
- CLI demo flows
- read-only wallet foundation

**Not in scope:**
- signing
- sending
- swap execution
- custody

---

### V1 — Connected wallet runway ✅ / in progress
**Goal:** the user stays in our app; Phantom only appears for connection and signing.

**Scope:**
- Connect Phantom
- Disconnect Phantom
- Sign message
- Minimal browser wallet cockpit (`/ui`)
- Send SOL (devnet-safe)
- Transaction state machine
- Preflight balance checks
- Support-mode errors
- Activity log
- Devnet funding helper / airdrop diagnostics

**Meaning of V1:**  
We have crossed from “read-only project” into “real wallet interaction surface.”

---

### V1.5 — Swap intelligence (Solana-first)
**Goal:** quote → compare → choose

**Scope:**
- in-app swap form
- quote provider integration on Solana
- route comparison UI
- clear display of:
  - spend
  - receive
  - estimated total swap cost
  - protections
  - path
  - recommendation
- default surface:
  - Recommended route
  - 2nd best
  - 3rd best
  - Direct route check

**This phase proves the product wedge.**

---

### V2 — Ranked comparison engine
**Goal:** turn the swap surface into a real execution-ranking product

**Scope:**
- rank routes using the same main selection metric
- show 2nd-best and 3rd-best transparently
- add direct-route comparison
- keep alternatives compact and expandable
- define cost model and breakdown math clearly
- make route comparisons more inspectable and more trustworthy

### Ranking roadmap
Phase 1 ranking can be built with **Jupiter-only quote APIs**.

Later phases should add:
- independent venue/provider quotes
- direct Raydium quotes
- direct Orca / SDK-based quotes
- other provider integrations as needed

This is how ranking becomes more robust and more honest over time.

---

### V2.5 — Swap execution (still non-custodial)
**Goal:** execute chosen route from inside our UI, while the connected wallet only signs.

**Scope:**
- route selection → transaction handoff
- wallet-signed execution
- status / confirmation UX
- no hidden wallet-layer markup as a product principle
- stronger support-mode diagnostics

---

### V3 — Small-swap optimization / support toolkit
**Scope:**
- optimize UX for small trades
- improve total-cost explanation
- improve route labeling / recommendation language
- benchmark against strong execution UX
- richer troubleshooting / failure explanation
- venue/provider comparisons as an advanced layer

---

### V4 — Multichain expansion
**Goal:** keep the same product wedge across more than one chain.

**Scope:**
- expand quote / comparison beyond Solana
- add other wallet connectors
- unify send / receive / swap UX across chains
- keep route transparency and low-overhead execution as the core value proposition

---

### V5 — Embedded self-custody (optional, advanced)
**Scope:**
- device-local encrypted key storage
- in-app signing
- security-heavy architecture

Only if it still fits the product strategy.

---

### V6 — Custodial rails (optional, only if strategic)
**Scope:**
- only if we ever choose to become a real custody / fintech product
- not part of the near-term plan

---

## Benchmarks / Reference Models

### Phantom
We learn from Phantom’s wallet UX and signing boundary.  
We do **not** want to inherit expensive or opaque swap UX as our product model.

### LlamaSwap
LlamaSwap is an important benchmark for the type of product thesis we care about:

- route aggregation mindset
- low / zero extra wallet-layer fee philosophy
- execution-first UX

For now, LlamaSwap is best treated as:

- benchmark
- inspiration
- comparison target

not yet as a guaranteed direct dependency.

### Solana route / venue ecosystem
Our route layer should be capable of explaining:

- which path is being used
- why it is being recommended
- how cost differs by route
- how alternatives compare
- when a direct route is meaningfully different from the recommended one

---

## Safety & Testing Policy
- We stay non-custodial in early versions
- We test transaction features in safe environments first
- We do not touch real-fund flows casually
- We prefer truthful failure over fake success

Project status remains **Alpha**.

Suggested path to **Beta**:
- stable read-only state
- stable send flows
- stable quote comparison UX
- clear docs
- basic tests
- support-grade error handling

---

## Architecture at a Glance

```mermaid
flowchart LR
  subgraph Data["Data & State"]
    B[(balance_snapshots)]
    P[(price_snapshots)]
    H[(portfolio_snapshots)]
  end

  subgraph Engine["Python Engine"]
    E[portfolio.py]
    DB[db.py]
  end

  subgraph API["FastAPI"]
    A[api/main.py]
  end

  subgraph UI["Browser UI"]
    U[/ui HTML + JS]
  end

  subgraph Wallet["Wallet Boundary"]
    W[Phantom / connected wallet]
  end

  subgraph Routing["Swap / Comparison Layer"]
    Q[Quote providers]
    C[Comparison logic]
    X[Execution handoff]
  end

  B --> E
  P --> E
  H --> A
  E --> A
  DB --> A

  A --> U
  U --> W

  U --> Q
  Q --> C
  C --> X
  X --> W



Tech Stack

Python
 portfolio engine
 API layer
 refresh scripts
 persistence logic
 ranking / comparison logic
SQLite
 balances
 prices
 portfolio snapshots
 history-first architecture
HTML + JavaScript
 current browser UI
 wallet integration
 swap comparison UI
 future execution UX
Wallet adapter boundary
 browser-side wallet provider
 user-controlled signing
 no private key handling by us


--- Long-Term Product Sentence

Web3 Digest aims to become an execution-intelligence layer for swaps, wrapped in a wallet-like experience — starting on Solana, making execution transparent and low-cost, and helping users compare, understand, and choose the best route without hidden wallet-layer markup.