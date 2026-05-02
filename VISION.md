# Web3 Digest — Vision

## What Web3 Digest is

Web3 Digest is a **wallet-connected execution-intelligence layer for Solana swaps**.

It is **not** a new wallet competing with Phantom.

Instead, the product sits **on top of trusted wallets like Phantom**. Users connect their wallet, keep Phantom as the signing and security layer, and use Web3 Digest to make better swap decisions through clearer quote comparison, cost visibility, route inspection, and execution transparency.

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
  - quote comparison
  - execution clarity
  - benchmark/reference comparison
  - cost visibility
  - route-shape explanation
  - direct-route inspection
  - support-style diagnostics
  - later, selected swap execution through Phantom
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

Build the most trusted, user-friendly **swap execution-intelligence layer** in crypto:

- simple enough for non-crypto-native users
- transparent enough for power users
- practical enough to sit on top of real wallets people already use

Over time, Web3 Digest should feel like the place you go **before you swap**, because it helps you understand what is really happening, what your real options are, and whether the route you are about to take is actually good.

---

## Near-term product focus

The immediate focus is **swap execution transparency on Solana**.

This includes:

- theoretical/reference baseline
- real quote preview
- multi-universe quote comparison
- recommended route
- direct-route comparison
- alternatives from distinct quote universes
- route-shape explanation
- execution gap versus reference
- separate visibility for route fees and network fee when available
- honest product notes when data or routing coverage is limited
- quote-only versus executable status
- a clean path from quote intelligence into future Jupiter execution

The swap surface is the wedge.

---

## Product principles

### 1. No custody

Web3 Digest should not try to become the wallet of record.

Users connect Phantom or another supported wallet. The wallet remains the signer and security anchor.

### 2. Transparency over blind execution

The product should not just say “best route.” It should explain:

- what route is being used
- what quote universe produced it
- why it was selected
- how it compares to alternatives
- how it compares to a theoretical/reference baseline
- whether a direct route exists as a simpler comparison lens
- whether the route is executable or quote-only

### 3. Honest product behavior

If something is unavailable, unsupported, stale, incomplete, comparison-only, quote-only, or estimated, the UI should say so clearly.

### 4. No fake quotes

Only real successful quotes should render as visible route cards.

Unsupported venues should fail softly and stay in diagnostics/debug output.

### 5. Separation of reference vs execution

The product should clearly distinguish between:

- **theoretical/reference pricing**
- **real quoted output**
- **real executable output once execution is added**

These are different layers and should remain separated in both product logic and user experience.

### 6. Honest cost framing

The product should keep cost explanation simple and trustworthy.

That means:

- keep the benchmark/transparency line separate from explicit route-cost language
- show the gap versus reference clearly
- show known cost components separately where available
- keep route fees separate when explicitly available
- keep network fee separate when estimated
- avoid pretending to know fee breakdowns that are not truly disclosed

### 7. Build on strong existing rails

The product should leverage trusted wallets and strong routing/liquidity ecosystems first, then expand intelligently where transparency and comparison create real value.

### 8. Mobile-aware by default

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
- what they are actually being quoted
- how much they are giving up versus the theoretical/reference value
- whether the recommended route is direct or complex
- what meaningful alternatives exist
- what venue or quote universe produced each option
- which routes are quote-only versus executable
- what the currently known cost story looks like

A key product insight is that **router-reported price impact** and the **gap versus the theoretical/reference value** are not the same metric. Both matter.

Another key product distinction is that:

- **quoted output vs reference** is a transparency metric
- **known explicit costs** are a route-cost metric

Those should not be collapsed into one vague number.

---

## Current comparison universe direction

Web3 Digest started Jupiter-first, but the product should not stop at one provider worldview.

The product is now moving toward a **multi-universe execution comparison engine**.

Current and near-term quote surfaces include:

- Jupiter
- Raydium
- Orca
- Meteora DLMM
- Phantom quote research
- PumpSwap curated paths

The long-term goal is not to become a prettier wrapper around one router.

It is to become a better **execution-intelligence layer** that helps users compare meaningful execution surfaces honestly.

---

## Product structure

### Layer 1 — wallet-connected input experience

- connect Phantom
- choose tokens
- type amount
- see live theoretical/reference conversion

### Layer 2 — execution intelligence

- request quotes
- compare recommended route vs alternatives
- inspect direct-route lens
- understand route shape and protections
- understand quote gap versus reference
- see known swap-cost components clearly
- show route fees and network fee separately where possible
- show which routes are executable versus quote-only
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
- understand unsupported venues

### Execute

The user wants to:

- choose a route
- start the swap flow
- hand off to wallet signing
- move from comparison into action

These behaviors should remain separate.

### Current intended actionability order

1. **Recommended Jupiter route becomes actionable first**
2. **Direct route becomes actionable second if technically executable**
3. **Alternatives become richer/selectable later only when execution paths are honest**

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

## Routing and execution direction

The first execution target should be **Jupiter through Phantom**.

That means:

- keep Jupiter as the first executable path
- keep Phantom as the signing boundary
- keep other universes quote-only until execution paths are real
- do not add execution buttons for routes the app cannot actually execute

After Jupiter execution works, Web3 Digest can evaluate additional executable universes such as Raydium, Orca, Meteora, or other honest paths.

The long-term goal is broader execution intelligence, not a one-router wrapper.

---

## Token coverage direction

The current curated token list is useful for proving the product thesis, but manual token additions should not become the long-term model.

The next scalable direction should be:

1. support pasted token mints
2. resolve token metadata dynamically
3. test which quote universes support the pair
4. later add token search
5. later add trending/liquidity discovery

The product should not become manual token data entry.

---

## Benchmark direction

The benchmark/reference layer should keep improving over time.

Future direction includes:

- keeping fresh reference logic honest
- supporting stronger long-tail / meme-token reference sources
- improving trust in the comparison layer for non-CoinGecko-friendly pairs
- continuing to distinguish:
  - benchmark/reference transparency
  - quoted output
  - known user cost
  - executable output once execution is added

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
- the destination panel shows the theoretical/reference converted amount live
- executable quote comparison remains a separate action and comparison layer below that

So the final design goal is not “make it prettier first.”

It is:

**build the right behavior, trust model, interaction model, and architecture now so the future UI can sit on top of a strong engine.**

---

## Near-term UX direction

The quote surface is moving toward a clearer product structure:

- top reference/benchmark layer
- Recommended as the main route card
- Direct as the simpler route lens
- Alternatives as distinct quote/comparison universes
- diagnostics/debug details available but not dominant

The product should feel:

- compact
- understandable
- inspectable
- mobile-translatable
- trustworthy before executable

This means the user should be able to understand, in order:

1. what we recommend
2. what the direct/simpler route looks like
3. what the alternatives are
4. which options are executable versus quote-only
5. what known cost story the product is surfacing
6. what the benchmark/reference comparison says

This layered structure is part of the product vision, not just temporary UI formatting.

---

## What success should feel like

A good Web3 Digest experience should make a user feel:

- “I understand what I’m being offered.”
- “I can see whether this route is simple or complex.”
- “I can compare the recommended route against real alternatives.”
- “I understand the gap between the theoretical reference and the quoted result.”
- “I can see the known cost story clearly.”
- “I know which routes are quote-only and which can be executed.”
- “I am not being asked to execute blindly.”

That feeling of clarity is the product.

---

## North star

Web3 Digest should become the place users trust to answer:

**“Before I swap, what am I really getting, what are my real options, what does it cost, and is this route actually good?”**