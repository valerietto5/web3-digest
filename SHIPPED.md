# Shipped (High-level)

This file is the quick “what exists right now” snapshot.
Updated weekly (and after major milestones).

## Current demo flow (works today)
1) Insert balances (manual or Solana)
2) Insert prices (CoinGecko)
3) Print wallet report (CLI)

## Shipped milestones

### Phase 1 — Wallet engine + demo backbone ✅
- Balance snapshots (manual) → SQLite
- Price snapshots (CoinGecko) → SQLite
- Portfolio compute (positions + totals)
- Honest 24h deltas (30h tolerance rule)
- CLI wallet report
- Repo published on GitHub (manual upload path)

### Phase 2 — Solana read-only V0 ✅
- Solana RPC balance fetch:
  - SOL balance
  - SPL token balances
- `run_balances_to_db.py --source solana --address <pubkey>` writes to `balance_snapshots`
- SPL policy Option 1:
  - Unpriced SPL tokens grouped/hidden by default
  - `--show-unpriced` reveals full list
- Human-readable display labels:
  - SOL / USDC
  - SPL mints show as shortened labels by default

### Phase 3 — Token registry + SPL pricing (CoinGecko) ✅
- Added `token_registry.py`:
  - mint → `asset`, `symbol`, `name`, `coingecko_id`
- Solana balance normalization:
  - known mints → clean asset keys (e.g. `usdc`)
  - unknown mints → `spl:<mint>`
- SPL pricing support (CoinGecko via registry):
  - price by asset key (e.g. `bonk`)
  - price by SPL key (e.g. `spl:<mint>`) using mint → `coingecko_id`
- Fixed mint case-sensitivity end-to-end:
  - no lowercasing SPL mints in balance inserts or price fetch

### Wallet UX V0 (CLI-first) ✅

- Saved accounts file: `accounts.json`
- `wallet_cli.py --list-accounts` prints saved accounts (chain, address, default assets)
- Default assets: `wallet_cli.py --account <name>` uses `default_assets` when `--assets` is not provided
- `wallet_cli.py --save-account <name> --address <pubkey> --chain solana --assets ...` writes/updates `accounts.json`
- Swap entry V0 (redirect):
  - `wallet_cli.py --swap-from sol --swap-to usdc` prints a Jupiter swap URL
  - when `--account` has an address, it prints the wallet address too


## Not shipped yet (next up)
- DexScreener fallback pricing for allowlisted SPL tokens not on CoinGecko (opt-in), using mint/contract address → best pair by liquidity/volume → `priceUsd` (first target: SNP500 mint `3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump`)
- Portfolio history snapshots (new table) + `wallet_cli.py --history N`
- Export latest portfolio (`--json`, `--csv`)
- Multi-account UX polish (default account / nicer formatting)
- Swap UX polish (still redirect; optional amount/help)
- Safety ramp planning: devnet + faucets for transaction testing (later V1)


