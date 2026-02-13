import requests

import json

from datetime import datetime, timezone

COINGECKO_IDS = {"btc": "bitcoin", "eth": "ethereum"}

COINGECKO_IDS["usdc"] = "usd-coin"


FILENAME = "balances.json"

LOGFILE = "prices_log.jsonl"


def norm(s):
    return s.strip().lower()


def get_cmd():
    ALLOWED = {"d", "w", "b", "t", "q"}
    while True:
        cmd = input("Welcome to Vallets, select what you want to do: (q)uit; (d)eposit; (w)ithdraw; (b)alance; (t)ransfer: ")
        cmd = norm(cmd)
        if not cmd:
            print("type smth please")
            continue
        if cmd == "q":
            return "q"
        if cmd in ALLOWED:
            return cmd
        else:
            print("invalid comand")



def get_wallet_name(prompt):
    while True:
        name = input(prompt)
        name = norm(name)
        if not name:
            print("type smth please")
            continue
        if name == "c":
            return None
        if name.isalpha():
            return name
        else:
            print("invalid try again")

def get_positive_amount(prompt: str) -> float | None:
    while True:
        s = norm(input(prompt))
        if not s:
            print("type smth please")
            continue
        if s in ("q", "quit", "c"):
            return None
        try:
            amt = float(s)
        except ValueError:
            print("must be a number")
            continue
        if amt <= 0:
            print("must be above 0")
            continue
        return amt
       

def safe_load_balances():
    try:
        with open(FILENAME, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        clean = {}
        for k, v in data.items():
            clean[k] = float(v)
        return clean
    except FileNotFoundError:
        return {}
    
def save_balances(balances):
    with open(FILENAME, "w", encoding="utf-8") as f:
        json.dump(balances, f, indent=2, sort_keys=True)


def show_balances(balances):
    wallet = input("wallet name or 'vallet'/'all' to show all the balances: ")
    wallet = norm(wallet)
    if not wallet:
        print("type smth please")
        return None
    if wallet == "c":
        return None
    if wallet in ("vallet", "all"):
        return sorted(balances.items())
    if wallet in balances:
        return [(wallet, balances[wallet])]
    print("wallet not found")
    return None

def fmt_money(amount: float, symbol: str = "$") -> str:
    return f"{symbol}{amount:,.2f}"


def get_price(data, coin, currency, default=None): 
    coin = norm(coin)
    currency = norm(currency)
    price = data.get(coin, {}).get(currency, default)
    return price

def print_price(price, symbol="$", label=""):
    if price is None:
        if label:
            print(f"{label.upper()}: price missing")
        else:
            print("price missing")
        return
    if label: 
        print(f"{label.upper()}: {symbol}{price:,.2f}")
    else:
        print(f"{symbol}{price:,.2f}")

def fetch_prices(coins, currency="usd"):
    url = "https://api.coingecko.com/api/v3/simple/price"
    currency = norm(currency)
    ids = []
    for q in coins:
        cg_id = COINGECKO_IDS.get(q)        
        if not cg_id:
            continue
        if cg_id in ids:
            continue
        ids.append(cg_id)
    ids_str = ",".join(ids)
    if ids_str == "":
        return {}
    params = {"ids": ids_str, "vs_currencies": currency}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            return {}   
        out = {}
        seen = set()
        for q in coins:
            if q in seen:
                continue
            seen.add(q)
            cg_id = COINGECKO_IDS.get(q)
            if not cg_id:
                continue
            out[q] = data.get(cg_id, {})
        return(out) 
    except requests.RequestException:
        return {}
    

def save_snapshot(prices, currency):
    sort_keys = True
    keep = {}
    for q in prices:
        check = prices.get(q)
        if check is None:
            continue
        keep[q] = check
    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": currency,
        "prices": keep,
    }
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, sort_keys=True) + "\n")



def load_snapshots():
    snaps = []
    try:
       with open(LOGFILE, "r", encoding="utf-8") as f:
           for line in f:
               line = line.strip()
               if not line:
                   continue
               obj = json.loads(line)
               snaps.append(obj)
               
    except FileNotFoundError:
        return []




    return snaps


def parse_coins(s, allowed=None):
    if allowed is None:
        allowed = set(COINGECKO_IDS.keys())
    parts = s.split(",")
    ok = []
    bad = []
    
    for p in parts:
        c = norm(p)
        if c == "":
            continue
        if c in allowed:
            if c in ok:
                continue
            ok.append(c)
        else:
            if c in bad:
                continue
            bad.append(c)
    return ok, bad

    
    

def currency_symbol(currency):
   if currency == "":
       return None
   currency = norm(currency)
   if currency == "eur":
       return "€"
   elif currency == "usd":
       return "$"
   return ""     
