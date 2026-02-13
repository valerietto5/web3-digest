from wallet_helpers import (
    safe_load_balances,
    save_balances,  
    show_balances, 
    get_positive_amount, 
    get_wallet_name, 
    get_cmd,
    fmt_money
)
        
balances = safe_load_balances()


while True:
    cmd = get_cmd()

    if cmd == "q":
        print("see you soon")
        break

    elif cmd == "d":
        wallet = get_wallet_name("wallet to deposit into (letters) or c: ")
        if wallet is None:
            continue
        amt = get_positive_amount("amount to deposit (or c): ")
        if amt is None:
            continue
        balances[wallet] = balances.get(wallet, 0) + amt
        save_balances(balances)
        print(f"{wallet} ---> {fmt_money(balances[wallet])}")
        continue


    elif cmd == "w":
        wallet = get_wallet_name("wallet to withdraw from (letters) or c: ")
        if wallet is None:
            continue
        if wallet not in balances:
            print("wallet not found")
            continue
        amt = get_positive_amount("amount to withdaw (or c): ")
        if amt is None:
            continue
        if amt > balances[wallet]:
            print("not enough money")
            continue

        balances[wallet] -= amt
        save_balances(balances)
        print(f"{wallet} ---> {fmt_money(balances[wallet])}")
        continue

    elif cmd == "b":
        result = show_balances(balances)
        if result is None:
            continue
        for w, bal in result:
            print(w, "--->", fmt_money(bal))      

    

    elif cmd == "t":
        from_wallet = get_wallet_name("from wallet (letters) or c: ")
        if from_wallet is None:
            continue

        if from_wallet not in balances:
            print("from wallet not found")
            continue

        to_wallet = get_wallet_name("to wallet (letters) or c: ")
        if to_wallet is None:
            continue

        if to_wallet == from_wallet:
            print("cannot transfer to the same wallet")
            continue

        amt = get_positive_amount("amount to transfer (or c): ")
        if amt is None:
            continue

        if amt > balances[from_wallet]:
            print("not enough money")
            continue

        balances[from_wallet] -= amt
        balances[to_wallet] = balances.get(to_wallet, 0) + amt
        save_balances(balances)

        print("new balances:")
        print(from_wallet, "--->", fmt_money(balances[from_wallet]))
        print(to_wallet, "--->", fmt_money(balances[to_wallet]))

        continue
    else:
        print("invalid command")

