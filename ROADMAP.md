\# Roadmap (Weekly / Monthly)



This file is the “where we’re going next” plan.

Updated weekly on Friday.



\## Current phase: Solana read-only wallet V0 (non-custodial)



\### This week (W)

\- ✅ Solana balances to DB (`--source solana`)

\- ✅ Token registry (mint → symbol/name/asset)

\- ✅ Price mapping for SPL tokens via CoinGecko id

\- ✅ Wallet UX V0: saved accounts (`accounts.json`) + `--list-accounts`

\- ✅ Wallet UX V0: default assets per account (no need to type `--assets` every time)

\- ✅ Swap entry V0: redirect link generator (Jupiter)





\## Session log



\### 2026-02-19 (Thu) — Wallet UX V0 + Swap entry V0

Shipped:

\- Saved accounts: `accounts.json`

\- `wallet\_cli.py --list-accounts`

\- Default assets per account (no need to type `--assets` every run)

\- `wallet\_cli.py --save-account ...` to update `accounts.json` via CLI

\- Swap entry V0: `--swap-from/--swap-to` prints a Jupiter redirect link (+ prints account address when available)

\- generic run\_solana\_demo.bat reads address/assets from accounts.json; end-to-end Solana refresh + report.”



Notes:

\- Still non-custodial: no signing, no private keys handled.

\- Feels more “wallet-like” without leaving safe territory.





\## Next week (W+1) — Wallet-grade UX + history + pricing upgrades



\### Monday — Token metadata UX (readability)

\- Expand `token\_registry.py` (mint → symbol/name + optional coingecko\_id)

\- Ensure Solana balances map:

&nbsp; - known mints → friendly keys (`usdc`, later `bonk`, etc.)

&nbsp; - unknown → keep `spl:<mint>` but display shortened label in CLI

\- Output goal: SOL / USDC / BONK show as symbols, not raw mints



\### Tuesday — Pricing upgrade (memes)

\- Add \*\*DexScreener fallback\*\* for allowlisted SPL tokens not on CoinGecko

\- Strategy: mint/contract → pairs → pick best by liquidity/volume → use `priceUsd`

\- First target token: SNP500 mint `3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump`



\### Wednesday — Portfolio history (time series)

\- Add a new SQLite table for portfolio snapshots (total + per-asset values)

\- Update `run\_portfolio\_history.py` to write snapshots

\- Add `wallet\_cli.py --history N` to print last N snapshots



\### Thursday — Exports (recruiter candy)

\- Add `wallet\_cli.py --json` and `--csv`

\- Write to `exports/portfolio\_latest.json` and `exports/portfolio\_latest.csv`

\- Add `exports/` to `.gitignore` (or keep `sample\_exports/` with fake data)



\### Friday — Tests + polish + docs

\- Add 2–3 tiny sanity tests (mapping + DB insert + baseline lookup)

\- Tighten CLI output (optional: $ change per asset when baseline exists)

\- Update docs + DEVLOG/TECHNICAL\_DEEP\_DIVE maintenance





\## Later (V1)

\- Connect Phantom (wallet adapter) for non-custodial auth

\- Funding flow:

&nbsp; - Solana Pay request link/QR (V0-friendly)

&nbsp; - Phantom-signed transfer (V1)

\- In-app Jupiter quote preview (still Phantom signs)

\- Safe transaction testing:

&nbsp; - use Solana devnet/testnet + faucets before touching real funds





\## Later (V2)

\- More chains (after Solana is solid)

\- Support-mode diagnostics (error states, RPC issues, token mapping issues)

\- Docs + “integration support” toolkit framing



