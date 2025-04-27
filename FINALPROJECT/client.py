# client.py
import socket
import threading
import json
import sys
import numpy as np
import time
from scipy.signal import find_peaks
from scipy.interpolate import make_interp_spline
import matplotlib.pyplot as plt

class TradingClient:
    def __init__(self):
        self.host = None
        self.port = None
        self.BUFFER_SIZE = 2048
        self.portfolio = {}
        self.sock = None #normal socket for trading
        self.fl_sock = None #socket for federated learning

        #federated learning state
        self.weights = np.zeros(3)   # [w0, w1, w2]
        self.local_data = []         # list of (x vector, reward y)
        self.last_prices = {}        # symbol -> last seen price
        self.analytics = [] #data gathered for live graphing

    def init(self, host: str, port: int, buffer_size: int = 1024):
        self.host = host
        self.port = port
        self.BUFFER_SIZE = buffer_size

    def connect(self):
        if self.sock:
            self.sock.close()
        self.sock = socket.create_connection((self.host, self.port))

        if self.fl_sock: self.fl_sock.close()
        self.fl_sock = socket.create_connection((self.host, self.port))


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
        # if not self.portfolio:
        #     symbols = self.list_symbols()
        #     self.portfolio = {sym: (0, 0.0, 0.0, 0.0) for sym in symbols}
        #     print("Initialized portfolio with all symbols at 0 shares.")
        # else:
        print("Your portfolio:")
        for sym, info in self.portfolio.items():
            shares, price, pct, profit = info
            print(f"    • {sym}: {shares} @ ${price:.2f}   Δ {pct:+.1f}%   P&L ${profit:.2f}")
        net = self.compute_net_profit()
        print(f"Overall net profit:    ${net:.2f}")
        self.analytics.append(net)

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
        self.fl_sock.sendall((json.dumps(req)+"\n").encode())
        self.fl_sock.recv(self.BUFFER_SIZE)


    def pull_global_model(self):
        # send request
        req = {"cmd": "get_global_model"}
        self.fl_sock.sendall((json.dumps(req)+"\n").encode())

        while True:
            raw = self.fl_sock.recv(self.BUFFER_SIZE).decode().strip()
            try:
                resp = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # if no weights, break and use it
            #if "weights" in resp:
            self.weights = np.array(resp["weights"])
            print("[TRAINING] updated local weights to", self.weights)
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


    def fetch_portfolio(self, user: str):
        """
        Blocking: send get_portfolio, recv the response,
        decode JSON, store self.portfolio, return it.
        """
        req = {"cmd":"get_portfolio","user":user}
        self.sock.sendall((json.dumps(req)+"\n").encode())
        raw = self.sock.recv(self.BUFFER_SIZE).decode().strip()
        resp = json.loads(raw)
        if resp.get("status") != "ok":
            raise RuntimeError("get_portfolio failed: " + resp.get("msg",""))
        self.portfolio = resp["portfolio"]
        return self.portfolio



    def autotrade(self, user: str):
        # prepare symbols and last_prices
        self.pull_global_model()
        symbols = list(self.portfolio.keys())
        last_prices = {sym: info[1] for sym, info in self.portfolio.items()}
        while True:
            # fetch fresh portfolio
            self.sock.sendall((json.dumps({"cmd":"get_portfolio","user":user})+"\n").encode())
            time.sleep(5)  # give listen thread chance to process
            # decide for each symbol
            for sym in symbols:
                if sym not in self.portfolio:
                    continue
                curr_price = self.portfolio[sym][1]
                pct_change = self.portfolio[sym][2] 

                #decide action based on RL weights and current price change
                Δp = curr_price - last_prices[sym]
                x = np.array([1.0, Δp, 0])  # action is 0 for now (no action)
                pred_profit = self.weights.dot(x)

                if pred_profit > 0:  # if predicted profit is positive, buy
                    action, qty = "buy", 10
                elif pred_profit < 0:  # if predicted profit is negative, sell
                    action, qty = "sell", 10
                else:
                    action = None  # no action
                
                #execute the action if decided
                if action:
                    req = {"cmd": action, "user": user, "symbol": sym, "qty": qty}
                    self.sock.sendall((json.dumps(req) + "\n").encode())
                
                #update last seen price for the symbol
                last_prices[sym] = curr_price
                if action:
                    req = {"cmd":action, "user":user, "symbol":sym, "qty":qty}
                    self.sock.sendall((json.dumps(req)+"\n").encode())
                last_prices[sym] = curr_price

            # train federated model if enough samples
            if len(self.local_data) >= 5:
                for _ in range(5):
                    x, y = self.local_data.pop(0)
                    pred = self.weights.dot(x)
                    self.weights -= 0.01 * (pred - y) * x
                    
                # send update & pull global
                self.fl_sock.sendall((json.dumps({
                    "cmd":"update_model","user":user,"weights":self.weights.tolist()
                })+"\n").encode())
                print(f"sent to server: ", self.weights.tolist())
                self.fl_sock.recv(self.BUFFER_SIZE)
                # self.pull_global_model()
            time.sleep(1) #ensures that we can have the same shape for plots


    def plot_analytics(self, user):
        """
        Show a static plot of net profit vs. time after trading ends,
        with an additional line connecting the peaks to encapsulate the general shape.
        """
        if not self.analytics:
            print("No data to plot.")
            return

        plt.figure(figsize=(10, 6))
        x = list(range(len(self.analytics)))
        y = self.analytics

        #plot the original net profit data
        plt.plot(x, y, marker='o', color='green', label='Net Profit')

        #fit a smooth curve to the general shape of the graph
        if len(x) > 3:  # Ensure enough points for interpolation
            spline = make_interp_spline(x, y, k=3)  # Cubic spline
            smooth_x = np.linspace(min(x), max(x), 500)
            smooth_y = spline(smooth_x)
            plt.plot(smooth_x, smooth_y, color='green', alpha=0.7, label='General Shape')

        plt.title(f"Net Profit ($) for User {user}")
        plt.xlabel('Round')
        plt.ylabel('Net Profit ($)')
        plt.grid(True)
        plt.legend()
        plt.show()  #blocks until window closed


    def main(self):
        self.connect()
        user = input("Who are you?: ").strip()
        #register
        self.sock.sendall((json.dumps({"cmd":"register","user":user})+"\n").encode())
        
        
        raw = self.sock.recv(self.BUFFER_SIZE)
        resp = json.loads(raw)
        if resp.get("status")!="ok":
            print("Registration failed:", resp.get("msg"))
            return

        #if the server returned portfolio on register, pick it up:
        if "portfolio" in resp:
            self.portfolio = resp["portfolio"]
        else:
            # fallback: explicitly fetch it
            self.fetch_portfolio(user)
        # get initial portfolio

        print(f"Starting trading session for {user}...")
        #print initial portfolio
        threading.Thread(target=self.listen, daemon=True).start()

        # pull initial model
        self.pull_global_model()

        # start autotrade
        try:
            self.autotrade(user)
        except KeyboardInterrupt:
            print("\n[INFO] Trading interrupted by user.")

        #after you stop the trades by hitting ctrl+c, this will display the analytics plot
        self.plot_analytics(user)


if __name__ == "__main__":
    HOST, PORT = 'localhost', 50004
    client = TradingClient()
    client.init(HOST, PORT)
    client.main()

