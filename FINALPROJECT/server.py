import socket
import sched
import time
import threading
import json
import os

state_lock = threading.Lock()

class TradingServer:
    def __init__(self, host: str, port: int, stock_file: str, currency_file: str, clients_file: str):
        self.host = host
        self.port = port
        self.stock_file = stock_file
        self.currency_file = currency_file
        self.clients_file = clients_file
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.stock_info = {}
        self.currency_info = {}
        self.client_info = {}
        self.BUFFER_SIZE = 2048

        #federated learning state - weights hold buy, sell, hold weights
        self.global_weights = [0.0, 0.0, 0.0]  # [w0, w1, w2] - always initialized to 0
        self.updates = {}                       # user -> weights list

    def load_state(self):
        self.stock_info = load_json(self.stock_file, {})
        self.currency_info = load_json(self.currency_file, {})
        self.client_info = load_json(self.clients_file, {})

    def save_state(self):
        save_json(self.stock_file,    self.stock_info)
        save_json(self.currency_file, self.currency_info)
        save_json(self.clients_file,  self.client_info)

    def process_request(self, req, conn, stockfile, currencyfile, clientfile):
        cmd = req.get("cmd")

        if cmd == "register":
            user = req.get("user")
            if not user:
                conn.sendall(b'{"status":"error","msg":"no user"}\n')
                return
            with state_lock:
                if user in self.client_info:
                    conn.sendall(b'{"status":"ok","msg":"welcome","portfolio":' +
                                 json.dumps(self.client_info[user]).encode() + b'}\n')
                    return
                self.client_info[user] = {}
                save_json(clientfile, self.client_info)
            conn.sendall(b'{"status":"ok","msg":"registered"}\n')
            return

        if cmd == "get_portfolio":
            user = req.get("user")
            if not user:
                conn.sendall(b'{"status":"error","msg":"user required"}\n')
                return
            fresh = load_json(stockfile, {})
            with state_lock:
                global stock_info
                stock_info = fresh
                port = self.client_info.get(user, {})
                for sym, raw in list(port.items()):
                    entry = raw[:]
                    shares, basis, _, _ = entry
                    current_price = stock_info.get(sym, basis)
                    entry[1] = current_price
                    unreal = shares * (current_price - basis)
                    pct    = ((current_price - basis)/basis)*100 if basis else 0.0
                    entry[2] = round(pct, 2)
                    entry[3] = round(unreal, 2)
                    port[sym] = entry
                save_json(clientfile, self.client_info)
                updated = self.client_info[user]
            conn.sendall((json.dumps({"status":"ok","portfolio":updated}) + "\n").encode())
            return

        if cmd == "list_symbols":
            with state_lock:
                syms = list(self.stock_info.keys())
            conn.sendall((json.dumps({"status":"ok","symbols":syms}) + "\n").encode())
            return

        if cmd in ("buy","sell"):
            user, sym, qty = req.get("user"), req.get("symbol"), req.get("qty")
            if None in (user, sym, qty):
                conn.sendall(b'{"status":"error","msg":"user,symbol,qty required"}\n')
                return
            with state_lock:
                port = self.client_info.setdefault(user, {})
                raw = port.get(sym, [0,0,0,0])
                entry = raw[:]
                shares, basis, realized, _ = entry
                current_price = self.stock_info.get(sym, basis)
                if cmd == "buy":
                    new_shares = shares + qty
                    if new_shares > 200:
                        conn.sendall(b'{"status":"error","msg":"share limit exceeded"}\n')
                        return
                    entry[0] = new_shares
                    entry[1] = current_price
                else:
                    new_shares = shares - qty
                    if new_shares < 0:
                        conn.sendall(b'{"status":"error","msg":"not enough shares"}\n')
                        return
                    gain = qty * (current_price - basis)
                    entry[2] = round(realized + gain, 2)
                    entry[0] = new_shares
                    entry[1] = current_price
                if new_shares == 0:
                    port.pop(sym, None)
                else:
                    unreal = new_shares * (current_price - entry[1])
                    pct    = ((current_price - entry[1]) / entry[1]) * 100
                    entry[3] = round(unreal, 2)
                    entry[1] = current_price
                port[sym] = entry
                save_json(clientfile, self.client_info)
                updated = port
            conn.sendall((json.dumps({"status":"ok","msg":"portfolio updated","portfolio":updated}) + "\n").encode())
            return

        ##federated learning commands ##

        if cmd == "get_global_model":
            print(f"[SERVER] handing out global_weights = {self.global_weights}")
            conn.sendall((json.dumps({
            "status":"ok",
            "weights": self.global_weights
            }) + "\n").encode())
            return

        if cmd == "update_model":
            user = req.get("user")
            weights = req.get("weights")
            print(f"weights recieved from the client: ", weights)
            if user is None or weights is None:
                conn.sendall(b'{"status":"error","msg":"user,weights required"}\n')
                return
            self.updates[user] = weights
            conn.sendall(b'{"status":"ok","msg":"model received"}\n')
            # aggregate when all clients have sent updates
            #if set(self.updates.keys()) >= set(self.client_info.keys()): #this was never being triggered so i got rid of it
            K = len(self.updates)
            self.global_weights = [
                sum(w[i] for w in self.updates.values())/K
                for i in range(len(self.global_weights))
            ]
            self.updates.clear()
            print("→ aggregated global_weights:", self.global_weights)
            return

        else:
            conn.sendall(b'{"status":"error","msg":"unknown cmd"}\n')


    def handle_client(self, conn, addr):
        buffer = ""
        try:
            while True:
                data = conn.recv(self.BUFFER_SIZE).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n",1)
                    if not line.strip():
                        continue
                    try:
                        req = json.loads(line)
                    except json.JSONDecodeError:
                        conn.sendall(b'{"status":"error","msg":"bad json"}\n')
                    else:
                        self.process_request(req, conn,
                            self.stock_file, self.currency_file, self.clients_file)
        finally:
            conn.close()


    def reload_prices(self):
        UPDATE_INTERVAL = 5
        fresh = load_json(self.stock_file, {})
        with state_lock:
            global stock_info
            stock_info = fresh
        self.scheduler.enter(UPDATE_INTERVAL, 1, self.reload_prices)


    def serve_forever(self):
        self.load_state()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind((self.host, self.port))
        srv.listen()
        print(f"Server listening on {self.host}:{self.port}")
        self.scheduler.enter(0, 1, self.reload_prices)
        threading.Thread(target=self.scheduler.run, daemon=True).start()
        try:
            while True:
                conn, addr = srv.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        finally:
            self.save_state()
            srv.close()


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



if __name__ == "__main__":
    server = TradingServer(
        host='localhost', port=50004,
        stock_file='stocks.txt', currency_file='currency.txt', clients_file='clients.txt'
    )
    server.serve_forever()

