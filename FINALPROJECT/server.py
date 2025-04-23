import socket
import sched
import time
import threading
import json
from data_management import * 

class TradingServer:
    def __init__(self, host: str, port: int, stock_file: str, currency_file: str, clients_file: str):
        self.host = host
        self.port = port
        self.stock_file = stock_file
        self.currency_file = currency_file
        self.clients_file = clients_file
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.clients = {}
        self.clients_lock = threading.Lock()
        self.stock_info = {}
        self.currency_info = {}
        self.client_info = {}
        self.state_lock = threading.Lock()
        self.BUFFER_SIZE = 1024


    def load_state(self):
        self.stock_info = load_json(self.stock_file, {})
        self.currency_info = load_json(self.currency_file, {})
        self.client_info = load_json(self.clients_file, {})

    def save_state(self):
        save_json(self.stock_file, self.stock_info)
        save_json(self.currency_file, self.currency_info)
        save_json(self.clients_file, self.client_info)

    #handle all possible incoming requests from the client
    def process_request(self, req, conn, stockfile, currencyfile, clientfile):
        cmd = req.get("cmd")

        if cmd == "register":
            user = req.get("user")
            if not user:
                conn.sendall(b'{"status":"error","msg":"no user"}\n')
                return

            with state_lock: 
                if user in self.client_info:
                    conn.sendall(b'{"status":"ok","msg":"welcome","portfolio":' + json.dumps(self.client_info[user]).encode() + b'}\n')
                    return
                
                # create an empty portfolio for them
                self.client_info[user] = {}
                save_json(clientfile, self.client_info)

            conn.sendall(b'{"status":"ok","msg":"registered"}\n')
            return

        #for users to see their current portfolios
        if cmd == "get_portfolio":
            user = req.get("user")
            if not user:
                conn.sendall(b'{"status":"error","msg":"user required"}\n')
                return

            #reload latest prices if desired:
            fresh_prices = load_json(stockfile, {})
            with state_lock:
                global stock_info
                stock_info = fresh_prices

                port = self.client_info.get(user, {})
                for sym, raw in list(port.items()):
                    entry = raw[:]  
                    shares, basis, realized, _ = entry

                    #update the live price slot
                    current_price = stock_info.get(sym, basis)
                    entry[1] = current_price

                    #recompute only the unrealized P&L & %Δ - don't touch the total profit
                    unreal   = shares * (current_price - basis)
                    pct      = ((current_price - basis) / basis) * 100 if basis else 0.0
                    entry[2] = round(pct, 2)
                    entry[3] = round(unreal,  2)

                    port[sym] = entry

                #persist the updated client_info to clients.txt
                save_json(clientfile, self.client_info)
                updated_portfolio = self.client_info[user]

            # Send back the fresh, on‐disk‐synced portfolio
            resp = {
                "status":    "ok",
                "portfolio": updated_portfolio
            }
            conn.sendall((json.dumps(resp) + "\n").encode())
            return


        #update client portfolio (e.g. after a buy/sell)
        elif cmd in ("buy","sell"):
            user, sym, qty = req["user"], req["symbol"], req["qty"]
            if None in (user, sym, qty):
                conn.sendall(b'{"status":"error","msg":"user,symbol,qty required"}\n')
                return

            with state_lock:
                port = self.client_info.setdefault(user, {})
                #default entry: [0 shares, cost_basis=0, realized=0, unrealized=0]
                raw = port.get(sym, [0, 0, 0, 0])  # Default entry: [shares, basis, realized, unrealized]
                entry = raw[:]  # copy to avoid mutating original until ready
                shares, basis, realized, unrealized = entry
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
                    
                    #compute realized gain on these shares :contentReference[oaicite:4]{index=4}
                    gain = qty * (current_price - basis)
                    entry[2] = round(realized + gain, 2)
                    entry[1] = current_price #update client stock price
                    entry[0] = new_shares
                    

                #remove stock if nothing left - optional, might remove this 
                if new_shares == 0:
                    port.pop(sym, None)
                
                else:
                    #recompute unrealized P&L and %Δ :contentReference[oaicite:5]{index=5}
                    unreal = new_shares * (current_price - entry[1])
                    pct    = ((current_price - entry[1]) / entry[1]) * 100
                    entry[3] = round(unreal, 2)
                    entry[1] = current_price #update client stock price
                

                port[sym] = entry
                #persist to disk :contentReference[oaicite:6]{index=6}
                save_json(clientfile, self.client_info)
                updated = port  # this user’s refreshed portfolio

            #reply with the full, updated portfolio
            resp = {"status":"ok", "msg":"portfolio updated", "portfolio": updated}
            conn.sendall((json.dumps(resp) + "\n").encode())

        else:
            conn.sendall(b'{"status":"error","msg":"unknown cmd"}\n')


    #parse messages coming in from the client and hand them off to the process_request helper function
    def handle_client(self, conn, addr):
        buffer = ""
        try:
            while True:
                data = conn.recv(self.BUFFER_SIZE).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    try:
                        req = json.loads(line)
                    except json.JSONDecodeError:
                        conn.sendall(b'{"status":"error","msg":"bad json"}\n')
                    else:
                        self.process_request(req, conn, self.stock_file, self.currency_file, self.clients_file)
        finally:
            conn.close()


    def reload_prices(self):
        UPDATE_INTERVAL = 5
        fresh = load_json(self.stock_file, {})
        with state_lock:
            global stock_info
            stock_info = fresh
        # schedule next run
        self.scheduler.enter(UPDATE_INTERVAL, 1, self.reload_prices)
    

    def serve_forever(self):
        #boot up the server - run each client in its own thread - could be useful bc all clients need access to the server's stock price info - but changes must be done atomically
        self.load_state()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind((self.host, self.port))
        srv.listen()
        print(f"Server listening on {self.host}:{self.port}")

        #keep updating the stock prices in the background so we're sending updated info to the client
        self.scheduler.enter(0, 1, self.reload_prices)
        threading.Thread(target=self.scheduler.run, daemon=True).start()  # :contentReference[oaicite:14]{index=14}

        try:
            while True:
                conn, addr = srv.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        finally:
            self.save_state()
            print(f"Saving state...")
            srv.close()

if __name__ == "__main__":
    server = TradingServer(
        host='10.253.137.44', port=50004,
        stock_file='stocks.txt', currency_file='currency.txt', clients_file='clients.txt'
    )
    server.serve_forever()


