import threading 
from sched import scheduler
import time
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

def save_state(stockfile, currencyfile, clientfile):
    with state_lock:
        save_json(stockfile, stock_info)
        save_json(currencyfile, currency_info)
        save_json(clientfile, client_info)


def reload_prices(stockfile, interval):
    """Reload stock prices from disk into the global stock_info."""
    global stock_info
    # Load fresh JSON from file
    new_info = load_json(stockfile, {})  # uses json.load internally :contentReference[oaicite:3]{index=3}
    with state_lock:
        stock_info = new_info
    #updates every 1 second - probably tweak this but there's a latency tradeoff here
    scheduler.enter(interval, 1, reload_prices, (stockfile, interval))



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
                conn.sendall(b'{"status":"ok","msg":"welcome","portfolio":' + json.dumps(client_info[user]).encode() + b'}\n')
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
            conn.sendall(b'{"status":"error","msg":"user required"}\n')
            return

        # (Re)load latest prices if desired:
        fresh_prices = load_json(stockfile, {})
        with state_lock:  # ensure thread safety :contentReference[oaicite:3]{index=3}
            global stock_info
            stock_info = fresh_prices

            port = client_info.get(user, {})
            for sym, entry in port.items():
                shares, purchase_price, _, _ = entry
                current_price = stock_info.get(sym, purchase_price)
                entry[1] = current_price #updates the client with the current stock price
                pct    = (current_price - purchase_price) / purchase_price * 100
                profit = shares * (current_price - purchase_price)
                entry[2], entry[3] = round(pct,2), round(profit,2)

            # Persist the updated client_info to clients.txt
            save_json(clientfile, client_info)

            updated_portfolio = client_info[user]

        # Send back the fresh, on‐disk‐synced portfolio
        resp = {
            "status":    "ok",
            "portfolio": updated_portfolio
        }
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
        user, sym, qty = req["user"], req["symbol"], req["qty"]
        if None in (user, sym, qty):
            conn.sendall(b'{"status":"error","msg":"user,symbol,qty required"}\n')
            return

        with state_lock:
            port = client_info.setdefault(user, {})
            # Default entry: [0 shares, cost_basis=0, realized=0, unrealized=0]
            entry = port.get(sym, [0, 0.0, 0.0, 0.0])
            shares, basis, realized, _ = entry
            current_price = stock_info.get(sym, basis)

            if cmd == "buy":
                new_shares = shares + qty
                #recalculate average cost basis :contentReference[oaicite:3]{index=3}
                new_basis = ((shares * basis) + (qty * current_price)) / new_shares
                entry[0] = new_shares
                entry[1] = current_price #update client stock price

            else:  # sell
                new_shares = shares - qty
                if new_shares < 0:
                    conn.sendall(b'{"status":"error","msg":"not enough shares"}\n')
                    return
                # 3) Compute realized gain on these shares :contentReference[oaicite:4]{index=4}
                gain = qty * (current_price - basis)
                entry[2] = round(realized + gain, 2)
                entry[1] = current_price #update client stock price
                entry[0] = new_shares
                # Cost basis remains unchanged for remaining shares

            # 4) Remove stock if nothing left
            if new_shares == 0:
                port.pop(sym, None)
            else:
                # 5) Recompute unrealized P&L and %Δ :contentReference[oaicite:5]{index=5}
                unreal = new_shares * (current_price - entry[1])
                pct    = ((current_price - entry[1]) / entry[1]) * 100
                entry[3] = round(unreal, 2)
                entry[1] = current_price #update client stock price
                # Optionally store pct in a separate field if you wish

                port[sym] = entry

            # 6) Persist to disk :contentReference[oaicite:6]{index=6}
            save_json(clientfile, client_info)
            updated = port  # this user’s refreshed portfolio

        # 7) Reply with the full, updated portfolio
        resp = {"status":"ok", "msg":"portfolio updated", "portfolio": updated}
        conn.sendall((json.dumps(resp) + "\n").encode())

    else:
        conn.sendall(b'{"status":"error","msg":"unknown cmd"}\n')
