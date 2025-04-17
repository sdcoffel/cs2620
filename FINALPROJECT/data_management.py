import threading 
import os 
import json 

state_lock = threading.Lock()

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def load_state(stockfile, currencyfile, clientfile):
    global stock_info, currency_info, client_info
    stock_info    = load_json(stockfile, {})
    currency_info = load_json(currencyfile, {})
    client_info   = load_json(clientfile, {})

# ————— Core request handler (excerpt) —————
def process_request(req, conn, stockfile, currencyfile, clientfile):
    cmd = req.get("cmd")

    if cmd == "register":
        user = req.get("user")
        if not user:
            conn.sendall(b'{"status":"error","msg":"no user"}\n')
            return

        with state_lock: 

            if user in client_info:
                conn.sendall(b'{"status":"error","msg":"username taken"}\n')
                return
        
            # create an empty portfolio for them
            client_info[user] = {}
            save_json(clientfile, client_info)

        conn.sendall(b'{"status":"ok","msg":"registered"}\n')
        return

    # — Get current stock info
    elif cmd == "get_stocks":
        with state_lock:
            resp = {"status":"ok", "stocks": stock_info}
        conn.sendall((json.dumps(resp)+"\n").encode())

    # — Update a stock price
    elif cmd == "update_stock":
        sym   = req.get("symbol")
        price = req.get("price")
        if not sym or price is None:
            conn.sendall(b'{"status":"error","msg":"symbol & price required"}\n')
            return
        with state_lock:
            stock_info[sym] = price
            save_json(stockfile, stock_info)
        conn.sendall(b'{"status":"ok","msg":"stock updated"}\n')

    # — Get currency rates
    elif cmd == "get_rates":
        with state_lock:
            resp = {"status":"ok", "rates": currency_info}
        conn.sendall((json.dumps(resp)+"\n").encode())

    # — Update a currency rate
    elif cmd == "update_rate":
        pair = req.get("pair")   # e.g. "USD->EUR"
        rate = req.get("rate")
        if not pair or rate is None:
            conn.sendall(b'{"status":"error","msg":"pair & rate required"}\n')
            return
        with state_lock:
            currency_info[pair] = rate
            save_json(currencyfile, currency_info)
        conn.sendall(b'{"status":"ok","msg":"rate updated"}\n')

    # — Get a user’s portfolio
    elif cmd == "get_portfolio":
        user = req.get("user")
        if not user:
            conn.sendall(b'{"status":"error","msg":"user required"}\n')
            return
        with state_lock:
            port = client_info.get(user, {})
        conn.sendall((json.dumps({"status":"ok","portfolio":port})+"\n").encode())

    # — Update a user’s holdings (e.g. after a buy/sell)
    elif cmd in ("buy","sell"):
        user, sym, qty = req.get("user"), req.get("symbol"), req.get("qty")
        if None in (user, sym, qty):
            conn.sendall(b'{"status":"error","msg":"user,symbol,qty required"}\n')
            return

        with state_lock:
            # ensure user exists
            port = client_info.setdefault(user, {})

            # compute new holdings
            entry = port.get(sym, [0, stock_info.get(sym,0), 0.0, 0.0])
            shares, price_per_share, pct, profit = entry

            delta = qty if cmd=="buy" else -qty
            new_shares = shares + delta
            if new_shares < 0:
                conn.sendall(b'{"status":"error","msg":"not enough shares"}\n')
                return

            # update values
            entry[0] = new_shares
            entry[1] = stock_info.get(sym, price_per_share)
            # recompute pct & profit however you like…
            # e.g. entry[2] = 100*(entry[1] - some_basis)/some_basis
            #      entry[3] = new_shares * (entry[1] - basis)

            port[sym] = entry
            save_json(clientfile, client_info)

        conn.sendall(b'{"status":"ok","msg":"portfolio updated"}\n')

    else:
        conn.sendall(b'{"status":"error","msg":"unknown cmd"}\n')
