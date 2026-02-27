from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import requests


DEFAULT_SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


@dataclass(frozen=True)
class SolanaTokenBalance:
    mint: str
    amount_raw: int           # integer base units (no decimals applied)
    decimals: int
    amount_ui: float          # human-readable amount
    program_id: Optional[str] = None


def _rpc_call(rpc_url: str, method: str, params: list[Any]) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(rpc_url, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"Solana RPC error: {data['error']}")
    return data["result"]


def get_sol_balance_lamports(address: str, rpc_url: str = DEFAULT_SOLANA_RPC_URL) -> int:
    """
    Returns SOL balance in lamports (1 SOL = 1_000_000_000 lamports).
    """
    res = _rpc_call(rpc_url, "getBalance", [address, {"commitment": "confirmed"}])
    return int(res["value"])


def get_spl_token_balances(address: str, rpc_url: str = DEFAULT_SOLANA_RPC_URL) -> List[SolanaTokenBalance]:
    """
    Returns SPL token balances for the owner address using getTokenAccountsByOwner.

    Each token account includes:
    - mint
    - tokenAmount: { amount (string int), decimals (int), uiAmount/uiAmountString }
    """
    program_ids = [TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID]

    # Merge by mint (a wallet can have multiple token accounts per mint)
    merged: dict[str, SolanaTokenBalance] = {}

    for program_id in program_ids:
        res = _rpc_call(
            rpc_url,
            "getTokenAccountsByOwner",
            [
                address,
                {"programId": program_id},
                {"encoding": "jsonParsed", "commitment": "confirmed"},
            ],
        )

        for item in res.get("value", []):
            acct = item.get("account", {})
            data = acct.get("data", {})
            parsed = data.get("parsed", {})
            info = parsed.get("info", {})
            mint = info.get("mint")
            tok = info.get("tokenAmount", {})
            if not mint or not tok:
                continue

            amount_raw = int(tok.get("amount", "0"))
            decimals = int(tok.get("decimals", 0))

            ui_amt = tok.get("uiAmount")
            if ui_amt is None:
                ui_str = tok.get("uiAmountString", "0")
                amount_ui = float(ui_str)
            else:
                amount_ui = float(ui_amt)

            # ignore empty accounts
            if amount_raw == 0:
                continue

            prev = merged.get(mint)
            if prev is None:
                merged[mint] = SolanaTokenBalance(
                    mint=mint,
                    amount_raw=amount_raw,
                    decimals=decimals,
                    amount_ui=amount_ui,
                )
            else:
                # sum balances for same mint across multiple accounts / programs
                merged[mint] = SolanaTokenBalance(
                    mint=mint,
                    amount_raw=prev.amount_raw + amount_raw,
                    decimals=prev.decimals,  # decimals should match for same mint
                    amount_ui=prev.amount_ui + amount_ui,
                )

    return list(merged.values())