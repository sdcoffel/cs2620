import threading 
import os 
import json 

state_lock = threading.Lock()

#json functions 
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


#handle all possible incoming requests from the client
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

    #for users to see their current portfolios
    if cmd == "get_portfolio":
        user = req.get("user")
        if not user:
            conn.sendall(b'{"status":"error","msg":"user required"}\n'); return

        with state_lock:
            portfolio = client_info.get(user, {})
        resp = {"status":"ok", "portfolio": portfolio}
        conn.sendall((json.dumps(resp) + "\n").encode())
        return


    #grab currency rates
    elif cmd == "get_rates":
        with state_lock:
            resp = {"status":"ok", "rates": currency_info}
        conn.sendall((json.dumps(resp)+"\n").encode())

    #keep track of currency rates
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


    #update client portfolio (e.g. after a buy/sell)
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
            
            if new_shares == 0:
                # remove the stock entirely when holdings drop to zero
                port.pop(sym, None)
            else:
                # update the remaining holding
                entry[0] = new_shares
                entry[1] = stock_info.get(sym, price_per_share)
                # we'll need to eventually update percentage increase/decrease and profit here, but havent' gotten there yet
                port[sym] = entry

            save_json(clientfile, client_info)
            updated_portfolio = client_info[user]

        resp = {
            "status":      "ok",
            "msg":         "portfolio updated",
            "portfolio":   updated_portfolio
        }
        conn.sendall((json.dumps(resp) + "\n").encode())

    else:
        conn.sendall(b'{"status":"error","msg":"unknown cmd"}\n')
