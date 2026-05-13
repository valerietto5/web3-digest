#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from providers.token_holder_concentration import get_holder_concentration_rpc_config_status


def main() -> int:
    status = get_holder_concentration_rpc_config_status()
    print(f"Holder concentration RPC source: {status.get('source')}")
    print(f"Dedicated/custom RPC configured: {'yes' if status.get('url_configured') else 'no'}")
    print(f"Public fallback: {'yes' if status.get('using_public_fallback') else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
