# client.py
import socket
import threading
import json
import sys
import numpy as np

class TradingClient:
    def __init__(self):
        self.host = None
        self.port = None
        self.BUFFER_SIZE = 2048
        self.portfolio = {}
        self.sock = None

        #federated learning state
        self.weights = np.zeros(3)   # [w0, w1, w2]
        self.local_data = []         # list of (x vector, reward y)
        self.last_prices = {}        # symbol -> last seen price

    def init(self, host: str, port: int, buffer_size: int = 1024):
        self.host = host
        self.port = port
        self.BUFFER_SIZE = buffer_size

    def connect(self):
        if self.sock:
            self.sock.close()
        self.sock = socket.create_connection((self.host, self.port))

    def list_symbols(self) -> list[str]:
        self.sock.sendall((json.dumps({"cmd":"list_symbols"})+"\n").encode())
        resp = self.sock.recv(self.BUFFER_SIZE).decode().strip()
        return json.loads(resp).get("symbols", [])

    def compute_net_profit(self):
        net_realized   = 0.0
        net_unrealized = 0.0
        for shares, price, pct, profit in self.portfolio.values():
            net_unrealized += profit
        return net_realized + net_unrealized

    def print_portfolio(self):
        if not self.portfolio:
            print("No holdings yet.")
        else:
            print("Your portfolio:")
            for sym, info in self.portfolio.items():
                shares, price, pct, profit = info
                print(f"    • {sym}: {shares} @ ${price:.2f}   Δ {pct:+.1f}%   P&L ${profit:.2f}")
        net = self.compute_net_profit()
        print(f"Overall net profit:    ${net:.2f}")

    def record_sample(self, action: int, sym: str, last_price: float, current_price: float, realized: float):
        Δp = current_price - last_price
        x = np.array([1.0, Δp, action])
        self.local_data.append((x, realized))

    def train_local_model(self, lr=0.01, epochs=5):
        for _ in range(epochs):
            for x, y in self.local_data:
                pred = self.weights.dot(x)
                grad = (pred - y) * x
                self.weights -= lr * grad
        self.local_data.clear()

    def send_model_update(self, user: str):
        req = {"cmd":"update_model","user":user,"weights":self.weights.tolist()}
        self.sock.sendall((json.dumps(req)+"\n").encode())
        self.sock.recv(self.BUFFER_SIZE)


    def pull_global_model(self):
        # send request
        req = {"cmd": "get_global_model"}
        self.sock.sendall((json.dumps(req)+"\n").encode())

        while True:
            raw = self.sock.recv(self.BUFFER_SIZE).decode().strip()
            print("[DEBUG] pull_global_model raw:", raw)
            try:
                resp = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # if no weights, break and use it
            if "weights" in resp:
                self.weights = np.array(resp["weights"])
                print("[DEBUG] updated local weights to", self.weights)
                break

    def listen(self):
        buffer = ""
        while True:
            data = self.sock.recv(self.BUFFER_SIZE).decode()
            if not data:
                print("\n[-] Server closed connection.")
                sys.exit(0)
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n",1)
                if not line.strip(): continue
                msg = json.loads(line)
                if msg.get("status") == "ok" and msg.get("portfolio") is not None:
                    # before overwrite, record samples for each symbol
                    for sym, info in msg["portfolio"].items():
                        last_p = self.last_prices.get(sym, info[1])
                        action = 0  # unknown
                        # realized profit is info[2] but you may adjust based on your design
                        realized = info[3]
                        self.record_sample(action, sym, last_p, info[1], realized)
                        self.last_prices[sym] = info[1]
                    self.portfolio = msg["portfolio"]
                    self.print_portfolio()
                print("\n> ", end="", flush=True)

    def main(self):
        self.connect()
        user = input("Who are you?: ").strip()
        # Register
        self.sock.sendall((json.dumps({"cmd":"register","user":user})+"\n").encode())
        _ = self.sock.recv(self.BUFFER_SIZE)
        # get initial portfolio
        self.sock.sendall((json.dumps({"cmd":"get_portfolio","user":user})+"\n").encode())
        self.pull_global_model()

        print(
          "Commands:\n"
          "  portfolio           show your holdings\n"
          "  buy SYMBOL QTY      buy shares\n"
          "  sell SYMBOL QTY     sell shares\n"
          "  quit                exit\n"
        )

        threading.Thread(target=self.listen, daemon=True).start()
        BATCH_SIZE = 5

        while True:
            line = input("> ").strip()
            if not line: continue
            if line.lower() in ("quit","exit"): break
            parts = line.split()
            cmd = parts[0].lower()
            if cmd == "portfolio":
                self.sock.sendall((json.dumps({"cmd":"get_portfolio","user":user})+"\n").encode())
            elif cmd in ("buy","sell") and len(parts)==3 and parts[2].isdigit():
                sym, qty = parts[1].upper(), int(parts[2])
                self.sock.sendall((json.dumps({"cmd":cmd,"user":user,"symbol":sym,"qty":qty})+"\n").encode())
                # after server ack and listen updates portfolio & records samples
                if len(self.local_data) >= BATCH_SIZE:
                    self.train_local_model()
                    self.send_model_update(user)
                    self.pull_global_model()
            else:
                print("Unknown command. Try: portfolio, buy SYMBOL QTY, sell SYMBOL QTY, or quit")
        self.sock.close()
        print("Ending trading session...")

if __name__ == "__main__":
    HOST, PORT = 'localhost', 50004
    client = TradingClient()
    client.init(HOST, PORT)
    client.main()

