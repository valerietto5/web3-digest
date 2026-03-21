
## New `ROADMAP.md`

```markdown
# Roadmap (Weekly / Monthly)

This file is the “where we’re going next” plan.
Updated weekly on Friday.

## Current phase
**V1 runway shipped enough to move into V1.5 planning.**

We now have:
- read-only wallet foundation
- FastAPI layer
- browser UI
- Phantom connect/sign boundary
- Send SOL devnet path
- transaction state UI
- preflight balance checks
- activity log
- in-app devnet airdrop helper / diagnostics

The product is no longer “read-only portfolio with ambitions.”
It is now a real early wallet surface.

---

## This week — what we shipped

### High level
- ✅ Send SOL UI inside `/ui`
- ✅ Browser-side Solana transaction build
- ✅ Phantom sign/send integration path
- ✅ Send state machine
  - Draft
  - Awaiting Signature
  - Submitted
  - Confirmed / Failed
- ✅ Preflight insufficient-balance check
- ✅ Live devnet wallet balance display
- ✅ In-app devnet airdrop helper using RPC
- ✅ Activity log
- ✅ Better support-mode error translation
- ✅ Duplicate wallet UI bug fixed

### Honest current status
- Send flow is real
- Airdrop request path is real
- Main blocker is still **public devnet funding availability**
- We now know the problem is external faucet / RPC availability, not core app logic

---

## Current open items from this week
These are not blockers, just unfinished polish / packaging items:
- update docs
- update GitHub
- retry faucet with smaller amount / alternate provider path when useful
- eventually confirm full **Submitted → Confirmed** send path once devnet funding lands

---

## Session log

### 2026-03-13 (Fri) — weekly review / product reframing
Key decisions:
- keep the project **non-custodial**
- start **Solana-first**, not multichain-all-at-once
- sharpen the wedge around:
  - route transparency
  - no extra wallet-layer swap markup
  - better execution for small swaps
- treat LlamaSwap as a **benchmark / inspiration target**
- build the first swap-intelligence layer around a practical Solana route provider path
- keep Phantom as the **signing boundary**, not the swap store

---

## Next week (W+1) — V1.5 begins
# Solana Swap Intelligence v0
**Theme:** Quote → Compare → Choose

### Main goal
From inside `/ui`, let a user:
- choose a token pair and amount
- fetch route/quote data
- compare swap choices clearly
- understand which route looks best and why

### Definition of Done
A user can:
- open a swap section inside `/ui`
- select input token / output token / amount
- fetch a quote for a Solana swap
- see:
  - expected output
  - route / venue information
  - price impact
  - why a route is recommended
- get a clear “best choice” label for the current trade
- see honest failure messages if quote data cannot be fetched

**Important:** next week’s goal is primarily **swap intelligence and quote UX**, not full swap execution yet.

---

## Weekly plan for next week

### Monday — swap surface + UI cleanup
**Goal:** make the next sprint sane before we bolt on more logic.

- Refactor `/ui` enough to reduce HTML/JS chaos
  - at minimum: clean structure, less inline monster risk
- Add a new **Swap** card / section in `/ui`
- Inputs:
  - from token
  - to token
  - amount
- Keep it Solana-first
- Keep route state / quote state visually separate from send state
- If time:
  - add a small “route comparison” placeholder panel

**Parallel small task**
- retry faucet path only if easy:
  - smaller airdrop amount
  - alternate faucet/provider path

---

### Tuesday — quote integration (Solana)
**Goal:** get first real quote data into the app.

- Wire Solana quote provider path
- Fetch quote / route data for chosen pair
- Show basic quote result in UI
- Display:
  - input
  - output
  - route label
  - any available price impact / route metadata
- Add raw debug output first if needed, then simplify

---

### Wednesday — comparison UX
**Goal:** turn quote data into product value.

- Make the quote section human-readable
- Label the route clearly
- Add recommendation logic such as:
  - best value
  - lowest impact
  - best for small size
- Explain route choice in simple language
- Keep the UI honest:
  - no data → say so
  - partial quote → say so

---

### Thursday — support-mode swap diagnostics
**Goal:** make swap quoting feel trustworthy.

- Add helpful quote error states:
  - pair unsupported
  - no route found
  - RPC/provider timeout
  - provider unavailable
- Add swap-related activity log entries
- Add simple “why this route?” explanations
- If time:
  - add a comparison-friendly visual summary block

---

### Friday — docs / GitHub / next-step decision
**Goal:** package the sprint and choose the next layer.

- Update:
  - `VISION.md`
  - `ROADMAP.md`
  - `SHIPPED.md`
  - `TECHNICAL_DEEP_DIVE.md`
  - `README.md`
- Update GitHub with:
  - latest files
  - latest UI screenshots
  - current project status
- Decide whether the next sprint becomes:
  - **swap execution handoff**, or
  - **receive UX / send SPL**, depending on what is most stable

---

## After next week

### Near-term path A — Swap execution
If quote/comparison works well:
- let user choose a route
- prepare execution transaction
- hand it to the connected wallet for signing
- show status / confirmation

### Near-term path B — Receive UX + send SPL
If we want to round out the transaction surface first:
- receive UX
- copy address / QR
- send SPL tokens
- token-specific balance / decimals handling

### Near-term path C — Support toolkit
Keep deepening:
- route explanation
- cost breakdown
- failure diagnostics
- wallet/provider troubleshooting

---

## Strategic roadmap themes

### 1) Solana first, multichain later
We start with one strong execution playground, then expand.

### 2) Small swaps matter
The product wedge is strongest where wallet-layer markup hurts most:
- retail-small trades
- memecoin-sized activity
- price-sensitive execution

### 3) Wallet signs, app explains
The connected wallet should approve and sign.
Our app should:
- compare
- explain
- recommend
- diagnose

### 4) Benchmark against best execution UX
Use strong products as reference points for:
- route clarity
- no-extra-fee mindset
- transparent execution

---

## Risks / blockers to remember
- public devnet funding is unreliable
- public RPC limits are real
- giant inline UI structure is still fragile until cleaned further
- quote/execution integrations should stay modular so we can swap providers later

---

## What “success” looks like by the end of next week
By next Friday, the app should feel like:
- a wallet with a real route-comparison brain
- not just a wallet that can send SOL

That means a user should be able to say:

> “For this Solana trade, I can already see what my best option probably is — and the app tells me why.”

That is the bridge from wallet prototype to actual product.