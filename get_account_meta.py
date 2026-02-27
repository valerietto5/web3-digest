import json
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/get_account_meta.py <account>", file=sys.stderr)
        sys.exit(2)

    account = sys.argv[1]
    p = Path("accounts.json")
    if not p.exists():
        print("", end="")
        sys.exit(1)

    data = json.loads(p.read_text(encoding="utf-8"))
    meta = data.get(account, {})

    address = meta.get("address") or ""
    assets = meta.get("default_assets") or []
    # Output: address|asset1 asset2 asset3
    print(address)
    print(" ".join(assets))

if __name__ == "__main__":
    main()