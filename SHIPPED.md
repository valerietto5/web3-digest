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
- SOLana-first swap card in `/ui`
- token selectors
- amount input
- Preview Quote action
- Clear action
- live inline baseline update while typing
- backend quote preview flow through `/swap/quote`
- Jupiter-first quote engine
- quote comparison surface
- recommended route block
- up to two ranked alternative options
- direct-route check block
- raw quote debug JSON section
- state / status handling for quote flow
- activity logging for quote actions

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
- keep two additional alternatives where available
- keep direct route as a separate comparison lens

### Shipped route details
Each route block can already show:
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

The first honest cost framing is now present.

### Shipped
- “Estimated trade execution cost” concept
- benchmark shortfall vs fresh reference logic
- explicit route fees shown separately when available
- network fee shown separately
- note explaining that separate fee fields are not being folded into the headline blindly
- route price impact still shown separately from the reference gap

### Why this matters
This is exactly the type of trust-building product behavior we want:
- simple
- honest
- no fake decomposition
- no overclaiming of precision

---

## 10) Swap instructions path

The app also already includes the swap-instructions backend path.

### Shipped
- `/swap/instructions` endpoint
- Jupiter swap-instructions request flow
- authenticated request support through `x-api-key` when configured
- instruction normalization for frontend fee estimation flow

This means the app has already moved beyond quote-only backend plumbing and into instruction-aware infrastructure.

---

## 11) Network-fee estimation for swaps

Swap network-fee estimation is already live in the current UI flow.

### Shipped
- fetch swap instructions for the selected quote
- build transaction instructions client-side
- estimate fee from compiled transaction message
- show estimated network fee per option
- use connected Phantom wallet public key when available

### Current implementation note
This fee estimate currently relies on a **mainnet Helius RPC URL hardcoded in the frontend**.

So the capability is shipped, but the implementation still needs hardening.

---

## 12) Debug / support-mode visibility

The app already has strong debugging and inspection scaffolding.

### Shipped
- raw quote debug JSON
- activity log panel
- detailed status cards
- friendly HTTP / thrown-error handling paths
- route explanation text
- backend exception handler that returns useful trace info in development

This is valuable both for product development and for the project’s developer-support / integration-support angle.

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
10. estimating swap network fees  
11. exposing route/debug details honestly

That is a real shipped foundation.

---

## What is not shipped yet

To stay honest, these are **not** fully shipped yet:

- real swap execution flow from the swap card
- multi-provider ranking beyond Jupiter-first comparison
- full route-fee decomposition for every quote
- production-safe RPC/auth/config handling for all swap infra
- polished connected dashboard experience
- mobile-optimized UI
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

That is the current shipped state.