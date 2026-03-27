# Web3 Digest — Vision

## What Web3 Digest is

Web3 Digest is a **wallet-connected execution-transparency app** for crypto swaps.

It is **not** a new wallet competing with Phantom.

Instead, the product sits **on top of trusted wallets like Phantom**. Users connect their wallet, keep Phantom as the signing/security layer, and use Web3 Digest to make better swap decisions through clearer route comparison, cost visibility, and execution transparency.

---

## Core product identity

**Phantom remains the wallet. Web3 Digest becomes the intelligence layer.**

That means:

- Phantom handles:
  - wallet creation
  - custody and key security
  - transaction signing
  - trusted wallet UX

- Web3 Digest handles:
  - swap transparency
  - route comparison
  - execution clarity
  - cost visibility
  - later, a stronger connected dashboard / holdings experience

This is a product built **with** Phantom in mind, not **against** it.

---

## Mission

Help users make better swaps by making execution:

- understandable
- trustworthy
- transparent
- low-friction
- as low-cost as possible

---

## Vision

Build the most trusted, user-friendly **swap transparency layer** in crypto:

- simple enough for non-crypto-native users
- transparent enough for power users
- practical enough to sit on top of real wallets people already use

Over time, Web3 Digest should feel like the place you go **before you swap**, because it helps you understand what is really happening and whether the route you are about to take is actually good.

---

## Near-term product focus

The immediate focus is **110% on swap transparency**.

This includes:

- ideal / theoretical no-fee baseline
- executable quote preview
- recommended route
- alternative routes
- direct-route comparison
- route shape explanation
- cost and shortfall clarity
- honest product notes when data or routing coverage is limited

The swap surface is the wedge.

---

## Product principles

### 1. No custody
Web3 Digest should not try to become the wallet of record.

Users connect Phantom or another supported wallet. The wallet remains the signer and security anchor.

### 2. Transparency over blind execution
The product should not just say “best route.” It should explain:

- what route is being used
- why it was selected
- how it compares to alternatives
- how it compares to a theoretical ideal reference
- whether a direct route exists as a simpler comparison lens

### 3. Honest product behavior
If something is unavailable, unsupported, stale, or incomplete, the UI should say so clearly.

### 4. Separation of reference vs execution
The product should clearly distinguish between:

- **ideal/theoretical reference pricing**
- **real executable quotes**

These are different layers and should remain separated in both product logic and user experience.

### 5. Build on strong existing rails
The product should leverage trusted wallets and existing routing ecosystems first, then expand intelligently where transparency and comparison create real value.

---

## What makes the product different

Many wallet and swap products optimize for speed and convenience, but hide or compress too much of the execution story.

Web3 Digest should help users see:

- what they ideally should get
- what they are actually being offered
- how much they are giving up versus the ideal reference
- whether the recommended route is direct or complex
- what meaningful alternatives exist

A key product insight is that **router-reported price impact** and the **gap versus the ideal market baseline** are not the same metric. Both matter.

---

## Product structure

### Layer 1 — wallet-connected input experience
- connect Phantom
- choose tokens
- type amount
- see ideal/theoretical live conversion

### Layer 2 — execution intelligence
- request executable quotes
- compare recommended route vs alternatives
- inspect direct-route lens
- understand route shape and protections
- later add fuller cost breakdowns and venue-level transparency

This separation should stay central to the design.

---

## Wallet direction

Web3 Digest should provide a **wallet-connected, wallet-like experience**, but should not try to replace Phantom.

That means the later dashboard/portfolio layer can expand into:

- connected holdings view
- token balances
- activity/history
- clearer asset presentation
- charts / better token inspection
- better connected portfolio UX than a minimal wallet numbers-only view

But this should remain an extension of the connected-wallet experience, not a custody product.

---

## Routing direction

The first comparison layer is Jupiter-based, but the long-term product cannot stop at one routing universe.

The roadmap should expand beyond Jupiter into at least two additional routing / liquidity universes so that route comparison becomes more credible, richer, and less dependent on a single provider’s worldview.

---

## Platform direction

Web app first is the right path.

Why:

- faster iteration
- easier demoability
- easier GitHub showcase
- cleaner early product validation

At the same time, the product should stay **mobile-aware**.

This matters because many real users — especially in fast-moving meme/token environments — swap from their phones using Phantom mobile. Even if native mobile is not the first build, the long-term UX direction should translate well to mobile behavior and expectations.

---

## Near-term design direction

The current inline baseline row is a transitional UI.

The final swap input should evolve toward a more stacked, two-panel, wallet-connected swap experience where:

- the user types the source amount directly in the source token panel
- the destination panel shows the ideal/theoretical converted amount live
- executable quote comparison remains a separate action and comparison layer below that

So the final design goal is not “make it prettier first.”  
It is: **build the right behavior and architecture now so the future UI can sit on top of a strong engine.**

---

## North star

Web3 Digest should become the place users trust to answer:

**“Before I swap, what am I really getting, what are my real options, and is this route actually good?”**