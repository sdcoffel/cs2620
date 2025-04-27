# client.py
import socket
import threading
import json
import sys
import numpy as np
import time
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
        if not self.portfolio:
            print("No holdings yet.")
        else:
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
            if "weights" in resp:
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
                
                #this could be the fault with RL. all i'm doing is checking the price change and deciding to buy/sell based on that. there 
                #is no predictive power here, and since i am using a random noise model, the weights won't actually learn anything useful. so i either change the model or 
                #implement a capping out metric where we end once we make x amount of profit. 


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


    def plot_analytics(self):
        """
        Show a static plot of net profit vs. time after trading ends.
        """
        if not self.analytics:
            print("No data to plot.")
            return

        plt.figure(figsize=(10, 6))
        x = list(range(len(self.analytics)))
        y = self.analytics
        plt.plot(x, y, marker='o', color = 'green') # no explicit color
        plt.title('Net Profit Over Time')
        plt.xlabel('Round')
        plt.ylabel('Net Profit ($)')
        plt.grid(True)
        plt.show() # blocks until window closed


    def main(self):
        self.connect()
        user = input("Who are you?: ").strip()
        #register
        self.sock.sendall((json.dumps({"cmd":"register","user":user})+"\n").encode())
        _ = self.sock.recv(self.BUFFER_SIZE)
        # get initial portfolio

        print(
          "Commands:\n"
          "  portfolio           show your holdings\n"
          "  buy SYMBOL QTY      buy shares\n"
          "  sell SYMBOL QTY     sell shares\n"
          "  quit                exit\n"
        )

        threading.Thread(target=self.listen, daemon=True).start()
        self.sock.sendall((json.dumps({"cmd":"get_portfolio","user":user})+"\n").encode())
        time.sleep(0.2) #slight delay to let all the threads get set up
        # pull initial model
        self.pull_global_model()

        # start autotrade
        try:
            self.autotrade(user)
        except KeyboardInterrupt:
            print("\n[INFO] Trading interrupted by user.")

        #after you stop the trades by hitting ctrl+c, this will display the analytics plot
        self.plot_analytics()


if __name__ == "__main__":
    HOST, PORT = 'localhost', 50004
    client = TradingClient()
    client.init(HOST, PORT)
    client.main()



#if i buy when the price is low, and sell when the price is high, exactly, my running theory is that 
#the net profit field over time will look exactly like the GBM distribution. i have a feeling that the RL algorithm is going to follow it exactly. 
#could be very cool behavior, and at least somewhat predictable on my end. all i would need to do is tell it to cash out at one of the peaks. 
#update: i was right. the whole thing becomes very easy to predict if i give it favorable hyperparamters
#BIIIG ASSUMPTION HERE: if i use the current hyperparameters in GBM, i am assuming that the market tends to get better over time. this is a big assumption. 

