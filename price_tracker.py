from wallet_helpers import (
    fetch_prices,
    print_price,  
    get_price,
    save_snapshot,
    currency_symbol,
    parse_coins,
    norm,
)

coins_s = input("coins (comma separeted, e.g. btc, eth): ")
currency = input("currency (e.g. usd, eur): ")
currency = norm(currency)
symbol = currency_symbol(currency)
ok, bad = parse_coins(coins_s)

data = fetch_prices(ok, currency)

if not ok:
    print("no valid coins inserted")
    exit()

prices = {}

for coin in ok:
    price = get_price(data, coin, currency)
    prices[coin] = price
    print_price(price, symbol, coin)

if bad:
     print("ignored:", ", ".join(bad))


save_snapshot(prices, currency)
print("saved snapshot")
