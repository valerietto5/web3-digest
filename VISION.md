\# Web3 Digest — Vision (North Star)



\## Mission

Build a Phantom-like, \*\*non-custodial\*\* wallet experience (starting read-only) that:

\- teaches real engineering through a hands-on project

\- produces a clean GitHub showcase

\- supports landing a Phantom-style role (developer support / integration support)



\## North Star

A wallet-like experience where a user can:

1\) select/enter an address (or connect Phantom later)

2\) see real holdings + deltas + history

3\) initiate a swap via safe redirect (Jupiter/Meteora)

4\) support a \*\*new wallet/account lifecycle\*\* without custody (create in Phantom, fund safely)

…without ever handling seed phrases in our app (V0/V1).



\## Product Principles (rules we don’t break)

\- \*\*No custody in V0/V1:\*\* we do not handle seed phrases/private keys.

\- \*\*Truthful metrics:\*\* if data is missing/stale, we show `n/a`.

\- \*\*Clean upgrades:\*\* each version should be an additive layer, not a rewrite.

\- \*\*Wallet UX:\*\* default output is clean; debug mode exists.



\## Version Ladder



\### V0 — Read-only wallet (CLI-first)

\*\*Scope:\*\*

\- Fetch balances (Solana RPC): SOL + SPL tokens

\- Store snapshots (balances + prices) in SQLite

\- Compute portfolio values + 24h deltas (with tolerance)

\- Display clean report (CLI)

\- Swap entry: \*\*redirect\*\* to Jupiter/Meteora UI (no signing)

\- Optional “funding request” helper:

&nbsp; - generate a simple payment request (e.g., Solana Pay link/QR) to fund an address via Phantom



\*\*Not in scope (V0):\*\*

\- signing, sending transactions, custody

\- generating seed phrases / creating wallets inside our app



\### V1 — Connected wallet mode (still non-custodial)

\*\*Scope:\*\*

\- “Connect Phantom” style auth (sign message to prove ownership)

\- saved accounts + identity

\- transaction/activity viewer (read-only)

\- \*\*new wallet/account lifecycle (non-custodial):\*\*

&nbsp; - user creates a new account in Phantom

&nbsp; - app connects and displays it

&nbsp; - funding via Phantom-signed transfer (wallet adapter) or Solana Pay link/QR



\### V2 — Integrated experience

\*\*Scope:\*\*

\- Jupiter quote API in-app (show routes/quotes)

\- better UX + support-mode debugging tools

\- (later) build unsigned tx + hand off to Phantom for signing

\- multi-chain exploration (after Solana V0 is solid)



\## Safety \& Testing Policy

\- We stay non-custodial in V0 (Phantom handles keys/seed phrases).

\- Before any transactions/signing/swaps with real funds, we test in safe environments:

&nbsp; - Solana devnet/testnet + faucets (SOL + test tokens)

&nbsp; - Goal: validate flows (send, swap redirect, signing UX, errors) without risking real money.

\- Project status: Alpha now. We move toward Beta once setup/docs/UX/tests are stable enough for other people to run.





\## Safety + release labels



\- Current status: \*\*Alpha\*\* (read-only + DB snapshots + CLI UX; no signing)

\- We start using \*\*devnet + faucets\*\* when we implement any transaction/signing flow (V1).

\- “Beta” criteria (suggested): stable read-only balances/pricing/history/exports + clear docs + basic tests + error-handling, before enabling signing features.







\## Architecture at a glance



```mermaid

flowchart LR

&nbsp; A\[run\_balances\_to\_db.py] --> B\[(wallet.db: balance\_snapshots)]

&nbsp; C\[run\_prices\_to\_db.py] --> D\[(wallet.db: price\_snapshots)]

&nbsp; B --> E\[portfolio.py compute\_report]

&nbsp; D --> E

&nbsp; E --> F\[wallet\_cli.py output]

&nbsp; G\[providers/solana\_rpc.py] --> A

&nbsp; H\[providers/solana\_balance\_provider.py] --> A



