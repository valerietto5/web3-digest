# Web3 Digest — Vision

## What Web3 Digest is

Web3 Digest is a **wallet-connected execution-transparency app** for crypto swaps.

It is **not** a new wallet competing with Phantom.

Instead, the product sits **on top of trusted wallets like Phantom**. Users connect their wallet, keep Phantom as the signing and security layer, and use Web3 Digest to make better swap decisions through clearer route comparison, cost visibility, and execution transparency.

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
  - route-shape explanation
  - direct-route inspection
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

- theoretical reference baseline
- executable quote preview
- recommended route
- alternative routes
- direct-route comparison
- route-shape explanation
- execution gap versus reference
- separate visibility for route fees and network fee when available
- honest product notes when data or routing coverage is limited
- a clean path from quote intelligence into future execution

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
- how it compares to a theoretical reference
- whether a direct route exists as a simpler comparison lens

### 3. Honest product behavior
If something is unavailable, unsupported, stale, incomplete, or estimated, the UI should say so clearly.

### 4. Separation of reference vs execution
The product should clearly distinguish between:

- **theoretical reference pricing**
- **real executable quotes**

These are different layers and should remain separated in both product logic and user experience.

### 5. Honest cost framing
The product should keep cost explanation simple and trustworthy.

That means:

- keep the benchmark/transparency line separate from the cost headline
- show the gap versus reference clearly
- show **Estimated total swap cost** as a separate user-facing cost layer
- keep route fees separate when explicitly available
- keep network fee separate when estimated
- avoid pretending to know fee breakdowns that are not truly disclosed

### 6. Build on strong existing rails
The product should leverage trusted wallets and strong routing ecosystems first, then expand intelligently where transparency and comparison create real value.

### 7. Mobile-aware by default
Even in a web-first phase, the product should behave in ways that can translate cleanly to mobile.

That means:

- tap-first interaction patterns
- expandable sections instead of hover-dependent behavior
- compact, layered information hierarchy
- clear primary action targets
- reduced accidental-tap risk

---

## What makes the product different

Many wallet and swap products optimize for speed and convenience, but hide or compress too much of the execution story.

Web3 Digest should help users see:

- what they ideally should get
- what they are actually being offered
- how much they are giving up versus the theoretical reference
- whether the recommended route is direct or complex
- what meaningful alternatives exist
- what the route path and route shape actually look like
- what the currently known cost story looks like

A key product insight is that **router-reported price impact** and the **gap versus the theoretical market reference** are not the same metric. Both matter.

Another key product distinction is that:

- **Executable output vs reference** is a transparency metric
- **Estimated total swap cost** is a known-cost metric

Those should not be collapsed into one number.

---

## Product structure

### Layer 1 — wallet-connected input experience
- connect Phantom
- choose tokens
- type amount
- see live theoretical conversion

### Layer 2 — execution intelligence
- request executable quotes
- compare recommended route vs alternatives
- inspect direct-route lens
- understand route shape and protections
- understand execution gap versus reference
- see known swap-cost components clearly
- show route fees and network fee separately where possible
- later add fuller cost breakdowns and venue-level transparency

### Layer 3 — actionability
- first compare
- then understand
- then choose
- then execute

This progression should stay central to the design.

---

## Interaction philosophy

The product should not blur **inspection** and **execution**.

These are different user intentions.

### Inspect
The user wants to:
- expand details
- compare options
- understand costs
- inspect route shape
- review alternatives

### Execute
The user wants to:
- choose a route
- start the swap flow
- hand off to wallet signing
- move from comparison into action

These behaviors should remain separate.

### Current intended actionability order
1. **Recommended route becomes actionable first**
2. **Direct route becomes actionable second**
3. **Alternatives become richer/selectable later**

### Interaction rule
Primary actions should be attached to **buttons**, not whole-card taps.

That keeps the experience:
- safer on mobile
- clearer for the user
- less prone to accidental execution

---

## Wallet direction

Web3 Digest should provide a **wallet-connected, wallet-like experience**, but should not try to replace Phantom.

That means the later dashboard / portfolio layer can expand into:

- connected holdings view
- token balances
- activity/history
- clearer asset presentation
- charts / better token inspection
- better connected portfolio UX than a minimal wallet numbers-only view

But this should remain an extension of the connected-wallet experience, not a custody product.

Most importantly:

**the wallet layer is infrastructure; the swap-intelligence layer is the product.**

---

## Routing direction

The first comparison layer is **Jupiter-first**, which is the right first step.

But the long-term product cannot stop at one routing universe.

The roadmap should expand beyond Jupiter into at least two additional routing / liquidity universes so that route comparison becomes:

- more credible
- richer
- more honest
- less dependent on a single provider worldview

The long-term goal is not to become a prettier wrapper around one router.  
It is to become a better **execution-transparency layer**.

---

## Benchmark direction

The current benchmark layer is CoinGecko-first, which is appropriate for the present stage.

But the benchmark layer will need to improve over time.

Future direction includes:

- keeping fresh reference logic honest
- supporting DexScreener or similar for long-tail / meme assets
- improving trust in the comparison layer for non-CoinGecko-friendly pairs
- continuing to distinguish:
  - benchmark transparency
  - executable output
  - known user cost

The product should stay honest even when the benchmark is imperfect.

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

The current inline reference row is a transitional UI.

The final swap input should evolve toward a more stacked, two-panel, wallet-connected swap experience where:

- the user types the source amount directly in the source token panel
- the destination panel shows the theoretical converted amount live
- executable quote comparison remains a separate action and comparison layer below that

So the final design goal is not “make it prettier first.”  
It is:

**build the right behavior, trust model, interaction model, and architecture now so the future UI can sit on top of a strong engine.**

---

## Near-term UX direction

The quote surface is moving toward a clearer product structure:

- top transparency layer
- Recommended as the main card
- Alternatives nested under Recommended
- Direct as the lighter second card

The product should feel:

- compact
- understandable
- inspectable
- mobile-translatable
- trustworthy before executable

This means the user should be able to understand, in order:

1. what we recommend
2. what the direct/simpler route looks like
3. what the alternatives are if they choose to inspect them
4. what known cost story the product is surfacing
5. what the benchmark comparison says

This layered structure is part of the product vision, not just temporary UI formatting.

---

## What success should feel like

A good Web3 Digest experience should make a user feel:

- “I understand what I’m being offered.”
- “I can see whether this route is simple or complex.”
- “I can compare the recommended route against real alternatives.”
- “I understand the gap between the theoretical reference and the executable result.”
- “I can see the known cost story clearly.”
- “I am not being asked to execute blindly.”

That feeling of clarity is the product.

---

## North star

Web3 Digest should become the place users trust to answer:

**“Before I swap, what am I really getting, what are my real options, and is this route actually good?”**