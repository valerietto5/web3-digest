# Shipped — Web3 Digest

This file describes what is already working today.

Current status: **Alpha**

---

## Product identity

**Web3 Digest is a wallet-connected execution comparison engine for Solana swaps.**

It is not trying to replace Phantom as the wallet, signer, or custody layer.

Instead:

- Phantom handles wallet connection, signing, and custody
- Web3 Digest handles:
  - swap route comparison
  - execution transparency
  - benchmark/reference comparison
  - cost visibility
  - quote inspection
  - supported route prepare/preflight/submit
  - wallet-connected portfolio/dashboard flows
  - selected swap execution through Phantom

The current product wedge is:

**connect Phantom, compare swap outcomes honestly, explain costs clearly, then execute supported routes safely.**

---

## 1) Core app foundation

The app has a real working foundation:

- FastAPI backend
- browser UI served at `/ui`
- root endpoint at `/`
- health endpoint at `/health`
- accounts endpoint at `/accounts`
- portfolio latest endpoint at `/portfolio/latest`
- portfolio history endpoint at `/portfolio/history`
- refresh balances endpoint at `/refresh/balances`
- refresh prices endpoint at `/refresh/prices`
- swap token list endpoint at `/swap/tokens`
- swap inline baseline endpoint at `/swap/inline-baseline`
- swap quote endpoint at `/swap/quote`
- swap prepare endpoint at `/swap/execute/prepare`
- swap preflight endpoint at `/swap/execute/preflight`
- swap submit endpoint at `/swap/execute/submit`
- token resolve endpoint at `/tokens/resolve`
- swap instructions endpoint at `/swap/instructions`

This means the project is no longer just a CLI/backend experiment.

It is now a usable wallet-connected web app skeleton with a real swap-comparison engine.

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

The app can behave like a lightweight connected dashboard and portfolio cockpit, not just a script.

This dashboard layer is useful, but it is no longer the lead wedge. The lead wedge is now swap execution transparency.

---

## 3) Balance + price refresh flows

Refresh flows are implemented through API endpoints and backend scripts.

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

The Phantom-connected browser boundary is live.

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

This is important because the project has a real non-custodial wallet-connected boundary, not a fake placeholder.

---

## 5) Devnet Send SOL flow

The app supports a real browser-side **Send SOL on devnet** flow.

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

This proves the app can support a real wallet-connected transaction path.

That experience was important groundwork for the current guarded swap execution flow.

---

## 6) Swap transparency and execution surface

The swap product wedge is live as an executable Alpha for supported routes.

### Shipped

- Solana-first swap card in `/ui`
- token selectors
- amount input
- Preview Quote action
- Clear action
- live inline baseline update while typing
- backend quote preview flow through `/swap/quote`
- backend prepare/preflight/submit flow for supported providers
- Phantom signing for selected prepared transactions
- explorer link and submitted-state UI after success
- quote comparison surface
- recommended route card
- direct-route comparison card
- alternatives section
- raw/debug quote visibility
- state/status handling for quote flow
- activity logging for quote actions

### Current behavior

The swap surface can compare real quotes across multiple quote universes and execute supported routes through Phantom.

Only successful quote results render as visible route cards.

Unsupported venues fail softly and remain diagnostics/debug information.

---

## 7) Live theoretical reference baseline

The app supports the “ideal/reference” product behavior.

### Shipped

- inline live baseline updates while typing
- baseline refresh on:
  - amount input change
  - from-token change
  - to-token change
- reference pricing shown before quote request
- fresh reference/benchmark data in the quote response
- source/timestamp note for the reference price

### Current user-facing framing

The UI can show:

- what the user spends
- theoretical/reference output
- executable/quoted output vs reference
- source/timestamp note for the reference price

This is important because the comparison surface starts before the actual quote request.

---

## 8) Multi-universe quote engine

This is the biggest shipped milestone.

The app is no longer only a Jupiter route-variant prototype.

It now has a first version of a multi-universe Solana swap quote engine.

### Current quote universes

#### Jupiter

- quote + executable through Phantom where supported
- USDC -> SOL preflight passed and opened Phantom during reverse-route testing

#### Raydium

- real quote path
- executable through Phantom where supported
- live SOL -> BONK and SOL -> USDC swaps succeeded on Solana mainnet

#### Orca

- explicit pool candidate model
- only renders successful real quotes
- unsupported pairs fail softly
- executable through Phantom where supported
- native SOL wrapping fixed with `setNativeMintWrappingStrategy("ata")`
- SOL -> USDC executed successfully on Solana mainnet
- diagnostics detect wSOL transfer/sync/close behavior

#### Meteora

- DLMM-only curated quote path
- comparison-only
- non-clickable for now
- no fake DLMM pool candidates

#### Phantom

- wallet-routing quote research surface
- comparison-only
- non-clickable
- curated SOL-to-SPL support only

#### PumpSwap

- direct SOL <-> pump-token quote + execution where a canonical pool is discovered
- FIGURE and SNP500-style pump-token paths validated
- not a composed route engine yet; token -> SOL -> USDC composition is not shipped

### Why this matters

The product can now show that a swap is not one invisible black-box result.

It can compare recognizable execution universes while staying honest about unsupported routes.

---

## 9) Current token coverage

The current curated token set is enough to validate the product thesis across stable and meme-token routes.

### Supported route set

#### SOL → USDC

Broadly supported across major venues.

#### SOL → BONK

Supported across several quote universes where available.

#### SOL → WIF

Supported across Jupiter, Raydium, Orca, and Phantom where available.

#### SOL → POPCAT

Added as a curated Solana meme token.

#### SOL → CHAD

Added as a curated Solana meme token.

#### SOL → SPX6900

Added as a curated Solana meme token.

#### SOL → FIGURE

PumpSwap-only curated test token used to validate Pump.fun-style quoting.

#### Pasted external Solana mints

The app can recognize pasted Solana mints, resolve metadata and decimals safely, and quote temporary recognized tokens without mutating `TOKEN_META`.

Recent validated mint:

- SNP500: `3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump`

Validated live paths:

- USDC -> SNP500 through Jupiter on Solana mainnet
- SNP500 -> SOL through PumpSwap on Solana mainnet

### Current rule

The app does not fake support.

If a token/venue pair is unsupported, it fails softly and stays out of visible route cards.

---

## 10) Ranked swap comparison logic

The swap engine supports ranked comparison.

### Shipped behavior

- compare successful quote options
- rank by actual quoted receive amount
- promote strongest option according to current ranking rules
- preserve Recommended / Direct / Alternatives structure
- keep quote-only routes non-clickable
- keep unsupported venues out of visible cards
- preserve diagnostics for failed/unsupported universes

### Shipped route details

The comparison surface can show:

- estimated receive amount
- receive value in USD
- minimum received where available
- route label
- execution surface label
- route shape
- step count
- token path
- price impact
- slippage setting
- execution gap vs reference
- route fees when available
- estimated network fee when available
- human-readable route explanation

This is now a meaningful execution-transparency surface, not just a raw quote dump.

---

## 11) Swap cost framing V1

The first honest cost framing is present and materially improved.

### Shipped

- top transparency/reference layer:
  - user spend
  - reference output
  - quoted output vs reference
  - source/timestamp
- route-card cost story:
  - execution cost / benchmark gap where available
  - network cost where available
  - route fees where disclosed/available
- honest handling of undisclosed route fees:
  - do not fabricate route fees
  - show unavailable/not disclosed states
- route price impact kept separate from reference gap
- execution cost floored at zero when the quote beats the reference benchmark

### Why this matters

The product is already doing the core job:

- showing the route result
- showing the benchmark comparison
- showing the known cost story
- not pretending to know cost components it does not actually know

This is much closer to a real trust-building swap product.

---

## 12) Route-card structure

A major UI/UX structure is already shipped.

### Current structure

- Recommended route
- Direct route check
- Alternatives
- visible “Via X” execution-surface labeling
- quote-only vs clickable behavior fields
- raw/debug details available for inspection

### Current direction

Default visible card language prioritizes user-facing execution surfaces:

- Via Jupiter
- Via Raydium
- Via Orca
- Via Meteora
- Via Phantom
- Via PumpSwap

Internal route details belong in inspect/debug mode rather than as the main visible card language.

---

## 13) Swap instructions path

The app includes the swap-instructions backend path.

### Shipped

- `/swap/instructions` endpoint
- Jupiter swap-instructions request flow
- authenticated request support through `x-api-key` when configured
- instruction normalization for frontend/backend fee estimation flow

This means the app has moved beyond quote-only backend plumbing and into instruction-aware and execution-aware infrastructure.

The full production-grade swap engine is not shipped yet, but guarded Alpha execution is real.

---

## 14) Network-fee estimation for swaps

Swap network-fee estimation exists in the current UI/backend flow.

### Shipped

- fetch swap instructions for the selected quote
- estimate fee for the recommended route where available
- show estimated network fee in the recommended route cost breakdown
- fallback fee behavior when the preferred fee-estimation path is unavailable
- honest handling of unavailable or limited fee-estimation paths
- prepared-transaction preflight simulation before Phantom opens
- setup/rent diagnostics for Associated Token Account creation
- non-SOL input diagnostics for SOL fee/rent requirements
- native SOL wrapping diagnostics:
  - `has_system_transfer_to_wsol_account`
  - `has_token_sync_native`
  - `has_token_close_account`
  - `native_sol_wrap_complete`
  - `wsol_wrap_lamports_detected`

### Current implementation note

This fee estimate is useful, but not final-grade.

It still needs hardening before production-quality execution.

---

## 15) Debug / support-mode visibility

The app has strong debugging and inspection scaffolding.

### Shipped

- raw quote debug JSON
- visible preflight diagnostics JSON
- activity log panel
- detailed status cards
- friendly HTTP / thrown-error handling paths
- route explanation text where appropriate
- backend exception handler that returns useful trace info in development
- diagnostics for unsupported quote universes
- insufficient-funds / account-setup diagnostics before Phantom signing

This is valuable for product development and for the project’s developer-support / integration-support angle.

---

## 16) Testing / repo hygiene milestones

Recent local validation has improved confidence.

### Shipped

- sanity test suite covering core behavior
- registry tests for curated swap tokens
- tests for fail-soft unsupported quote behavior
- tests ensuring unsupported venues do not create fake cards
- tests covering quote-only/clickable behavior for supported universes
- tests covering provider prepare/preflight safety
- tests covering pasted-mint external-token recognition
- `AGENTS.md` repository guidelines for coding agents
- latest implementation checkpoints:
  - `0f3f15a` — Fix Orca native SOL wrapping
  - `343a2ba` — Support recognized external token swaps

Recent test checkpoint:

- `python3 -m unittest test_sanity.py`
- 299 tests passing
- Node syntax checks passed for Orca/PumpSwap helpers
- Python compile checks passed
- `git diff --check` passed

---

## What is true right now

Right now, Web3 Digest supports:

1. loading account data
2. refreshing balances and prices
3. showing holdings and history
4. connecting Phantom
5. signing messages
6. sending SOL on devnet
7. previewing Solana swap routes
8. comparing multiple quote universes
9. showing a theoretical/reference baseline
10. showing Recommended / Direct / Alternatives
11. showing quote-only versus clickable behavior
12. showing a clearer swap cost story
13. estimating swap network fees where available
14. exposing route/debug details honestly
15. failing softly when a universe does not support a pair
16. avoiding fake quote cards
17. executing supported Jupiter/Raydium/Orca/PumpSwap routes through Phantom
18. preflighting prepared transactions before Phantom opens
19. recognizing pasted Solana mints after safe decimal resolution
20. refreshing recognized external-token balances

That is a real shipped foundation.

---

## What is not shipped yet

To stay honest, these are **not** fully shipped yet:

- executable Meteora routes
- Phantom execution/handoff route
- full route-fee decomposition for every quote universe
- final-grade transaction-specific network-fee estimation
- token search / discovery
- composed routes like PumpSwap token -> SOL -> USDC
- duplicate recognized-token asset-list polish
- final external-token valuation/source warning UX
- random DexScreener mint and suspicious/scam mint testing
- Bubblemaps / holder concentration live UX testing
- final two-panel swap input UX
- polished connected dashboard experience
- mobile-optimized final UI
- multichain execution intelligence
- receive UX
- send SPL token flow

So the app is already real, but it is still **Alpha** and still clearly in build mode.

---

## Current conclusion

What exists today is not just a prototype idea.

Web3 Digest already has:

- a real backend
- a real browser UI
- a real Phantom connection boundary
- a real devnet send flow
- a real Solana swap quote/comparison surface
- real guarded swap execution through Phantom for Jupiter, Raydium, Orca, and PumpSwap direct paths
- a real multi-universe execution-transparency wedge
- a curated and pasted-mint meme-token test surface
- a first honest swap-cost explanation model
- a fail-soft trust philosophy

The product thesis is now visible in the working local app.

The next work is live regression testing, external-token polish, route/provider expansion planning, and production hardening.
