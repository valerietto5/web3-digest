# Shipped

This file describes what is already working today.

---

## Product identity

**Web3 Digest is a wallet-connected execution-transparency app.**

It is not trying to replace Phantom as the wallet, signer, or custody layer.

Instead:

- Phantom handles wallet connection, signing, and custody
- Web3 Digest handles:
  - route comparison
  - execution transparency
  - cost visibility
  - quote inspection
  - wallet-connected portfolio/dashboard flows

Current status: **Alpha**

---

## What is already shipped

## 1) Core app foundation

The app now has a real working foundation:

- FastAPI backend
- browser UI served at `/ui`
- root endpoint at `/`
- health endpoint at `/health`
- accounts endpoint at `/accounts`
- portfolio latest endpoint at `/portfolio/latest`
- portfolio history endpoint at `/portfolio/history`
- refresh balances endpoint at `/refresh/balances`
- refresh prices endpoint at `/refresh/prices`

This means the project is no longer just a CLI/backend experiment.  
It is now a usable wallet-connected web app skeleton.

---

## 2) Portfolio / dashboard foundation

The connected dashboard layer is already working.

### Shipped
- account loading from `accounts.json`
- latest portfolio report loading
- portfolio history loading
- holdings table in the UI
- summary pills for balances / prices / stale state
- total portfolio value display
- support for optional asset override
- support for optional “show unpriced”
- DB-backed snapshot flow through SQLite

### What this gives us
The app can already behave like a lightweight connected dashboard and portfolio cockpit, not just a script.

---

## 3) Balance + price refresh flows

Refresh flows are already implemented through API endpoints and backend scripts.

### Balances
- refresh balances from the UI
- Solana account refresh support
- cooldown support
- force refresh option
- automatic portfolio snapshot write after successful refresh

### Prices
- refresh prices from the UI
- CoinGecko-based refresh flow
- optional DexScreener fallback toggle in the UI
- minimum liquidity control for Dex fallback
- automatic portfolio snapshot write after successful refresh

This means the dashboard can stay alive and refreshable without manual DB editing.

---

## 4) Phantom wallet connection layer

The Phantom-connected browser boundary is already live.

### Shipped
- detect Phantom in browser
- connect Phantom
- eager trusted reconnect
- disconnect Phantom
- show connected wallet state
- show connected wallet address
- sign message flow
- signature preview display
- activity logging for wallet actions

This is important because the project now has a real non-custodial wallet-connected boundary, not a fake placeholder.

---

## 5) Devnet Send SOL flow

The app already supports a real browser-side **Send SOL on devnet** flow.

### Shipped
- recipient input
- amount input
- devnet-only send surface
- validation flow before send
- Phantom signing step
- app-side raw transaction submission
- confirmation step
- explorer link after submission
- live wallet balance refresh
- preflight balance check before wallet prompt
- fee-aware balance check
- clearer insufficient-balance handling
- airdrop button for devnet testing
- airdrop confirmation handling
- airdrop error translation for common faucet issues
- activity log coverage for send / airdrop actions

### Why this matters
This is no longer just “UI that looks like a wallet.”  
A real wallet-connected transaction path already exists.

---

## 6) Swap transparency surface

The swap product wedge is already live in quote-preview form.

### Current shipped swap surface
- Solana-first swap card in `/ui`
- token selectors
- amount input
- Preview Quote action
- Clear action
- live inline baseline update while typing
- backend quote preview flow through `/swap/quote`
- Jupiter-first quote engine
- quote comparison surface
- recommended route card
- nested alternatives inside the recommended card
- direct-route comparison card
- raw quote debug JSON section
- state / status handling for quote flow
- activity logging for quote actions

### Why this matters
The swap area is no longer just a raw quote block.  
It now has a real product hierarchy.

---

## 7) Live theoretical reference baseline

The app already supports the “ideal/reference” product behavior we wanted.

### Shipped
- inline live baseline updates while typing
- baseline refresh on:
  - amount input change
  - from-token change
  - to-token change
- reference pricing shown before executable quote request
- fresh CoinGecko-based reference in the quote response
- clearer reference wording in the UI

### Current user-facing framing
The UI now shows:
- what the user spends
- CoinGecko reference output
- executable output vs reference
- source/timestamp note for the reference price

This is an important product milestone because the comparison surface now starts before the actual executable quote.

---

## 8) Ranked swap comparison logic

The swap UI is already more than a single quote box.

### Shipped checked variants
- default Jupiter route
- broader search variant
- alternate venue-mix variant
- direct-route-only check

### Shipped comparison behavior
- compare checked variants
- rank by strongest checked output
- promote best checked option to “Recommended”
- keep additional alternatives where available
- keep direct route as a separate comparison lens

### Shipped route details
The comparison surface can already show:
- estimated receive amount
- minimum received
- route label
- route shape
- step count
- token path
- price impact
- slippage setting
- execution gap vs reference
- explicit route fees when available
- estimated network fee
- human-readable route explanation

This is already a meaningful execution-transparency surface, not just a raw quote dump.

---

## 9) Swap cost framing V1

The first honest cost framing is now present and materially improved.

### Shipped
- separate **top transparency layer**:
  - You spend
  - CoinGecko reference
  - Executable output vs reference
  - source/timestamp
- separate **cost layer** in the Recommended card
- **Estimated total swap cost** headline for the recommended route
- expandable cost breakdown for the recommended route:
  - execution cost
  - network cost
  - route fees
- honest handling of undisclosed route fees:
  - `not disclosed for this swap`
- network cost shown in USD
- route price impact kept separate from the reference gap
- execution cost floored at zero when the route beats the reference benchmark

### Why this matters
The product is now doing what it is supposed to do:

- showing the route result
- showing the benchmark comparison
- showing the known cost story
- not pretending to know cost components it does not actually know

This is much closer to a real trust-building swap product.

---

## 10) Recommended / Alternatives / Direct card structure

A major UI/UX checkpoint is now shipped.

### Shipped structure
- Recommended is the primary card
- Alternatives are nested under Recommended
- Alternatives are compact and expandable
- Direct route is a lighter second card
- the old heavier 3-section structure has been simplified

### Shipped compact-alternatives behavior
Alternative rows currently show:
- route name
- receive amount
- execution cost
- shape / step count

They are currently informative-only.

### Shipped Direct-card simplification
The Direct card now:
- keeps the route comparison visible
- removes most of the heavier fee/debug clutter
- behaves more like a true second comparison card
- uses shorter note language

### Why this matters
The quote surface is now much more:
- compact
- understandable
- mobile-friendly
- product-like

This is one of the biggest UX milestones shipped so far.

---

## 11) Tiny-cost formatting improvement

Cost formatting is already cleaner than before.

### Shipped
- very small USD costs are no longer shown with overly noisy 6-decimal formatting
- tiny costs now display more compactly, for example:
  - `$0.0004`
  - instead of overly verbose forms like `$0.000420`

### Why this matters
The numbers stay truthful but become easier to scan.

---

## 12) Swap instructions path

The app also already includes the swap-instructions backend path.

### Shipped
- `/swap/instructions` endpoint
- Jupiter swap-instructions request flow
- authenticated request support through `x-api-key` when configured
- instruction normalization for frontend/backend fee estimation flow

This means the app has already moved beyond quote-only backend plumbing and into instruction-aware infrastructure.

---

## 13) Network-fee estimation for swaps

Swap network-fee estimation is already live in the current UI flow.

### Shipped
- fetch swap instructions for the selected quote
- estimate fee for the recommended route
- show estimated network fee in the recommended route cost breakdown
- fallback fee behavior when the preferred fee-estimation path is unavailable
- honest handling of unavailable or limited fee estimation paths

### Current implementation note
This fee estimate is live and useful, but still not final-grade.

It still needs future hardening and refinement for stronger execution-quality confidence.

---

## 14) Debug / support-mode visibility

The app already has strong debugging and inspection scaffolding.

### Shipped
- raw quote debug JSON
- activity log panel
- detailed status cards
- friendly HTTP / thrown-error handling paths
- route explanation text where appropriate
- backend exception handler that returns useful trace info in development

This is valuable both for product development and for the project’s developer-support / integration-support angle.

---

## 15) Interaction model groundwork

The app now implicitly supports the first real interaction-model layer for the swap surface.

### Shipped direction reflected in the UI
- expand and inspect behavior is already separated from execution behavior
- alternatives are currently inspect-only
- the card hierarchy already reflects future actionability order:
  - Recommended first
  - Direct second
  - Alternatives later

### Why this matters
Even though the swap is not executable yet from the quote cards, the UI structure is now being built in a way that supports future actionability cleanly.

---

## What is true right now

Right now, Web3 Digest already supports:

1. loading account data  
2. refreshing balances and prices  
3. showing holdings and history  
4. connecting Phantom  
5. signing messages  
6. sending SOL on devnet  
7. previewing swap routes on Solana  
8. comparing multiple checked route shapes  
9. showing a theoretical reference baseline  
10. showing a recommended card, nested alternatives, and a direct-route lens  
11. showing a clearer swap cost story for the recommended route  
12. estimating swap network fees for the recommended route  
13. exposing route/debug details honestly  

That is a real shipped foundation.

---

## What is not shipped yet

To stay honest, these are **not** fully shipped yet:

- real swap execution flow from the swap cards
- CTA buttons for Recommended / Direct routes
- selectable or executable alternatives
- multi-provider ranking beyond Jupiter-first comparison
- full route-fee decomposition for every quote
- final-grade transaction-specific network-fee estimation
- production-safe swap infra hardening in every path
- two-panel swap input UX
- polished connected dashboard experience
- mobile-optimized final UI
- multichain execution intelligence
- receive UX
- send SPL token flow

So the app is already real, but it is still **Alpha** and still clearly in build mode.

---

## Bottom line

What exists today is not just a prototype idea.

Web3 Digest already has:

- a real backend
- a real browser UI
- a real Phantom connection boundary
- a real devnet send flow
- a real Solana swap quote/comparison surface
- a real execution-transparency wedge
- a meaningful product-quality quote hierarchy
- a first honest swap-cost explanation model

That is the current shipped state.