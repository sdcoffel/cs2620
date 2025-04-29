import socket
import threading
import json
import sys
import numpy as np
import time
from scipy.interpolate import make_interp_spline
import matplotlib.pyplot as plt


class TradingClient:
    def __init__(self):
        """Initializes the client object state variables.
        Args: None
        Attributes:
            host (str): The hostname or IP address of the server. Defaults to None.
            port (int): The port number for the server connection. Defaults to None.
            BUFFER_SIZE (int): The buffer size for socket communication. Defaults to 2048.
            portfolio (dict): A dictionary to track the portfolio, where each key is a stock symbol and the value is a list containing [shares, cost_basis, realized P&L, unrealized P&L].
            sock (socket.socket): A socket object for trading-related communication. Defaults to None.
            fl_sock (socket.socket): A socket object for federated learning communication. Defaults to None.
            weights (numpy.ndarray): A NumPy array representing the weights for federated learning, initialized to [0, 0, 0].
            local_data (list): A list of tuples, where each tuple contains an input vector (x) and a reward (y).
            last_prices (dict): A dictionary mapping stock symbols to their last seen prices.
            analytics (list): A list to store data for live graphing and analytics.
            loss_history (list): A list to store the loss history for training.
            accuracy (list): A list to store the accuracy for each round of training.
        
        Returns: None
        """

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
        self.loss_history = []   #losses for each round of training
        self.accuracy = [] #accuracy for each round of training


    def init(self, host: str, port: int, buffer_size: int = 1024):
        """Initializes the client with the specified host, port, and buffer size.

        Args:host (str): The hostname or IP address of the server to connect to.
            port (int): The port number on which the server is listening.
            buffer_size (int, optional): The size of the buffer for receiving data. Defaults to 1024.

        Return: None
        """

        #update host and port info 
        self.host = host
        self.port = port
        self.BUFFER_SIZE = buffer_size


    def connect(self):
        """Establishes connections for both trading and federated learning sockets.
        Args: None
        Returns: None
        """

        #for trading: close any preexisting sockets and fire up a new one 
        if self.sock:
            self.sock.close()
        self.sock = socket.create_connection((self.host, self.port))

        #ditto for federated learning 
        if self.fl_sock:
            self.fl_sock.close()
        self.fl_sock = socket.create_connection((self.host, self.port))


    def list_symbols(self) -> list[str]: 
        """
        Sends a request to the server to retrieve a list of available stock symbols.
        Args: None
        Returns: list[str]: A list of stock symbols available for trading.
        """

        self.sock.sendall((json.dumps({"cmd": "list_symbols"}) + "\n").encode())
        resp = self.sock.recv(self.BUFFER_SIZE).decode().strip()
        return json.loads(resp).get("symbols", [])


    def compute_net_profit(self):
        """
        Computes the overall net profit by summing up realized and unrealized profits.

        Args: None
        Returns: float: The total net profit (realized + unrealized).
        """

        #calculate net profit and return it 
        net_realized = 0.0
        net_unrealized = 0.0
        for shares, price, pct, profit in self.portfolio.values():
            net_unrealized += profit
        return net_realized + net_unrealized


    def print_portfolio(self):
        """
        Prints the current portfolio, including shares, price, percentage change, and profit for each stock.
        Also computes and displays the overall net profit, appending it to the analytics data.
        
        Args: None
        Returns: None
        """

        print("Your portfolio:")
        #pretty printing
        for sym, info in self.portfolio.items():
            shares, price, pct, profit = info
            print(f"    • {sym}: {shares} @ ${price:.2f}   Δ {pct:+.1f}%   P&L ${profit:.2f}")

        #grab the value of the net profit and return it
        net = self.compute_net_profit()
        print(f"Overall net profit:    ${net:.2f}")
        return net


    def record_sample(self, action: int, sym: str, last_price: float, current_price: float, realized: float):
        """
        Records a sample for training the local model.

        Args:
            action (int): The action taken (e.g., 0 for no action, 1 for buy, -1 for sell).
            sym (str): The stock symbol.
            last_price (float): The last observed price of the stock.
            current_price (float): The current price of the stock.
            realized (float): The realized profit or loss.

        Returns: None
        """

        #record the sample for training
        #action = 0 for no action, 1 for buy, -1 for sell
        #realized = profit or loss from the action taken
        Δp = current_price - last_price
        x = np.array([1.0, Δp, action])
        self.local_data.append((x, realized))


    def send_model_update(self, user: str):
        """
        Sends the updated local model weights to the server for federated learning.
        Args: user (str): The username of the client.
        Returns: None
        """

        req = {"cmd": "update_model", "user": user, "weights": self.weights.tolist()}
        self.fl_sock.sendall((json.dumps(req) + "\n").encode())
        self.fl_sock.recv(self.BUFFER_SIZE)


    def pull_global_model(self):
        """
        Requests and retrieves the global model weights from the server, updating the local model.
        Args: None
        Returns: None
        """

        #send request to get the global model
        req = {"cmd": "get_global_model"}
        self.fl_sock.sendall((json.dumps(req) + "\n").encode())

        #wait for the server to respond with the global model
        while True:
            raw = self.fl_sock.recv(self.BUFFER_SIZE).decode().strip()
            try:
                resp = json.loads(raw)
            except json.JSONDecodeError:
                continue

            #update local weights with the received global weights
            self.weights = np.array(resp["weights"])
            print("[TRAINING] Updated local weights to", self.weights)
            break


    def listen(self):
        """Listen for incoming messages from the server and process them. Runs in a separate thread.
        Args: None
        Returns: None
        """

        buffer = ""
        #continuously listen for messages from the server
        while True:
            data = self.sock.recv(self.BUFFER_SIZE).decode()
            if not data:
                print("\n[-] Server closed connection.")
                sys.exit(0)
            buffer += data

            #process each line of the buffer - if buffer contains newline, split into lines 
            while "\n" in buffer:
                line, buffer = buffer.split("\n",1)
                if not line.strip(): continue
                msg = json.loads(line)
                if msg.get("status") == "ok" and msg.get("portfolio") is not None:
                    #before overwrite, record samples for each symbol
                    for sym, info in msg["portfolio"].items():
                        #if we have a last price for the symbol, record the sample
                        last_p = self.last_prices.get(sym, info[1])
                        action = 0  
                        realized = info[3]
                        self.record_sample(action, sym, last_p, info[1], realized)
                        self.last_prices[sym] = info[1]
                    self.portfolio = msg["portfolio"]


    def fetch_portfolio(self, user: str):
        """Fetches the portfolio for a given user by sending a request to the server.

        This is a blocking operation that sends a "get_portfolio" command with the
        specified user, waits for the server's response, decodes the JSON response,
        and stores the portfolio in the `self.portfolio` attribute.

        Args: user (str): The username for which to fetch the portfolio.
        Returns: dict: The portfolio data for the specified user.
        Raises: RuntimeError: If the server response indicates a failure, with the error message provided in the response.
        """

        #send request to get the portfolio
        req = {"cmd":"get_portfolio","user":user}
        self.sock.sendall((json.dumps(req)+"\n").encode())
        raw = self.sock.recv(self.BUFFER_SIZE).decode().strip()
        #parse the response
        resp = json.loads(raw)
        if resp.get("status") != "ok":
            raise RuntimeError("get_portfolio failed: " + resp.get("msg",""))
        #update the portfolio attribute with the response
        self.portfolio = resp["portfolio"]
        return self.portfolio


    def autotrade(self, user: str):
        """
        Automatically trades stocks for a given user based on a reinforcement learning model.
        This runs in an infinite loop, periodically fetching portfolio data and making trading decisions. 
        It uses federated learning to update the global model with locally trained weights.
        Continuously fetches the user's portfolio and evaluates trading decisions for each stock symbol.
        Calculates the predicted profit for each stock based on the current price change and RL model weights.
        Executes buy or sell actions if the predicted profit is positive or negative, respectively.
        Updates the last seen price for each stock symbol after making a decision.
        Trains the local reinforcement learning model using collected data samples when enough samples are available.
        Sends updated model weights to the server and pulls the global model weights for synchronization.
        
        Args: user (str): The username of the trader.
        Returns: None
        """

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

                if pred_profit > 0:  #if predicted profit is positive, buy
                    action, qty = "buy", 10
                elif pred_profit < 0:  #if predicted profit is negative, sell
                    action, qty = "sell", 10
                else:
                    action = None  #no action
                
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

            #train federated model locally and send weights to the server
            losses = []
            correct = 0
            total = 0 

            for _ in range(5):
                x, y = self.local_data.pop(0)
                pred = self.weights.dot(x)
                #update weights using gradient descent
                self.weights -= 0.01 * (pred - y) * x

                #did we predict the right action? postitive y means we made a profit, negative y means we lost 
                actual = 1 if y > 0 else (0 if y == 0 else -1)
                guess  = 1 if pred > 0 else (0 if pred == 0 else -1)
                if guess == actual:
                    correct += 1
                total += 1

                #compute losses 
                loss = (pred - y) ** 2
                losses.append(loss)
                self.loss_history.append(np.mean(losses))

                #compute accuracy
                accuracy = correct / total if total > 0 else 0
                self.accuracy.append(accuracy)
                print(f"[TRAIN] accuracy = {accuracy:.4f} ({correct}/{total})")

                #compute net 
                net = self.print_portfolio()
                self.analytics.append(net)
                print(f"[TRAIN] average MSE = {np.mean(losses):.4f}")
                
            #send update & pull global
            self.fl_sock.sendall((json.dumps({"cmd":"update_model","user":user,"weights":self.weights.tolist()})+"\n").encode())
            print(f"sent to server: ", self.weights.tolist())
            self.fl_sock.recv(self.BUFFER_SIZE)
            time.sleep(1) #ensures that we can have the same shape for plots


    def plot_analytics(self, user):
        """
        Uses matplotlib to plot the net profit over time for a given user.
        At the end of the trading session, we show a static plot of net profit over time after trading ends,
        with an additional line connecting the peaks to encapsulate the general shape.

        Args: username 
        Retuns: None
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
        if len(x) > 3:  #ensure enough points for interpolation
            spline = make_interp_spline(x, y, k=3)  # cubic spline
            smooth_x = np.linspace(min(x), max(x), 500)
            smooth_y = spline(smooth_x)
            plt.plot(smooth_x, smooth_y, color='green', alpha=0.7, label='General Shape')

        plt.title(f"Net Profit ($) for User {user}")
        plt.xlabel('Round')
        plt.ylabel('Net Profit ($)')
        plt.grid(True)
        plt.legend()
        plt.show()  #blocks until window closed


    def plot_loss(self, user): 
        """
        Creates a line plot of the MSE for each round of training.
        Args: username
        Returns: None
        """

        if not self.loss_history:
            print("No loss data to plot.")
            return

        plt.figure(figsize=(10, 6))
        plt.plot(self.loss_history, marker='o', color='red', label='Loss History')
        plt.title(f"Loss History Over Training Rounds for user {user}")
        plt.xlabel('Round')
        plt.ylabel('Average Loss')
        plt.grid(True)
        plt.legend()
        plt.show()


    def plot_accuracy(self, user):
        """
         After trading, show how often each local‐model's step predicted the right trade to make.

         Args: username 
         Returns: None
        """

        if not self.accuracy:
            print("No accuracy data to plot.")
            return

        rounds = list(range(len(self.accuracy)))
        plt.figure(figsize=(10,6))
        plt.plot(rounds, self.accuracy, marker='o', label='Accuracy', color='blue')
        plt.ylim(0,1)
        plt.title(f"Local‐Training Accuracy per Round for user: {user}")
        plt.xlabel('Training Round')
        plt.ylabel('Accuracy')
        plt.grid(True)
        plt.legend()
        plt.show()       


    def main(self):
        """Main driver function to run the trading client."""

        self.connect()
        user = input("Who are you?: ").strip()

        #register the username
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
            #fallback: explicitly fetch it
            self.fetch_portfolio(user)

        #get initial portfolio
        print(f"Starting trading session for {user}...")
        threading.Thread(target=self.listen, daemon=True).start()

        #pull global model from server
        self.pull_global_model()

        #start autotrade loop
        try:
            self.autotrade(user)
        except KeyboardInterrupt:
            print("\n[INFO] Trading interrupted by user.")

        #after hitting ctrl+c, this will display the analytics plot
        self.plot_analytics(user)

        #show the loss plot 
        self.plot_loss(user)

        #show the accuracy plot 
        self.plot_accuracy(user)


if __name__ == "__main__":
    """Main entry point for the trading client."""

    #this only works for harvard public wifi (as usual) - so put that as the host
    HOST = input("Enter the server IP address: ").strip()
    PORT = input("Enter the server port number: ").strip()
    client = TradingClient()
    client.init(HOST, PORT)
    client.main()

