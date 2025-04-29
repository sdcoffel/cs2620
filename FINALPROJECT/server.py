import socket
import sched
import time
import threading
import json
import os

state_lock = threading.Lock()

class TradingServer:
    def __init__(self, host: str, port: int, stock_file: str, currency_file: str, clients_file: str):
        """
        Initializes the server with the specified host, port, and file paths for stock, currency, and client data.
        Also sets up the scheduler, initializes data structures for stock, currency, and client information,
        and prepares the federated learning state vars.

        Args: host (str): The hostname or IP address for the server.
            port (int): The port number for the server.
            stock_file (str): Path to the file containing stock information.
            currency_file (str): Path to the file containing currency information.
            clients_file (str): Path to the file containing client information.

        Attributes:
            host (str): The hostname or IP address for the server.
            port (int): The port number for the server.
            stock_file (str): Path to the file containing stock information.
            currency_file (str): Path to the file containing currency information.
            clients_file (str): Path to the file containing client information.
            scheduler (sched.scheduler): Scheduler instance for managing timed events.
            stock_info (dict): Dictionary to store stock information.
            currency_info (dict): Dictionary to store currency information.
            client_info (dict): Dictionary to store client information.
            BUFFER_SIZE (int): Buffer size for network communication.
            global_weights (list): List representing global weights for federated learning [buy, sell, hold].
            updates (dict): Dictionary mapping users to their respective weight updates.

        Returns: None
        """
        
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
        """
        Loads the state of the server from the stock, currency, and client files.
        This method initializes the stock_info, currency_info, and client_info dictionaries
        with the data stored in their respective files.
        
        Args: None
        Returns: None
        """

        #load the state from the files, if they don't exist, create them with empty dicts
        self.stock_info = load_json(self.stock_file, {})
        self.currency_info = load_json(self.currency_file, {})
        self.client_info = load_json(self.clients_file, {})


    def save_state(self):
        """
        Saves the current state of the server to the stock, currency, and client files.
        This method writes the stock_info, currency_info, and client_info dictionaries
        to their respective files in JSON format.

        Args: None
        Returns: None
        """

        #save the state to the files
        save_json(self.stock_file,    self.stock_info)
        save_json(self.currency_file, self.currency_info)
        save_json(self.clients_file,  self.client_info)


    def process_request(self, req, conn, stockfile, currencyfile, clientfile):
        """
        Handles client requests and performs various operations based on the command provided in the request.
        
        Args:  req (dict): The request dictionary containing the command and other parameters.
            conn (socket): The client connection socket for sending responses.
            stockfile (str): Path to the file containing stock information.
            currencyfile (str): Path to the file containing currency information.
            clientfile (str): Path to the file containing client portfolio information.
        Supported Commands:
            - "register": Registers a new user or welcomes an existing user. Initializes a portfolio with default shares.
            - "get_portfolio": Retrieves the user's portfolio, updating it with the latest stock prices.
            - "list_symbols": Lists all available stock symbols.
            - "buy": Buys a specified quantity of shares for a user, updating their portfolio.
            - "sell": Sells a specified quantity of shares for a user, updating their portfolio.
            - "get_global_model": Retrieves the global model weights for federated learning.
            - "update_model": Updates the global model with weights provided by the client.
        Notes:
            - The function uses a state lock to ensure thread-safe operations on shared resources.
            - Responses are sent back to the client in JSON format.
            - For "buy" and "sell" commands, share limits and availability are validated.
            - For federated learning commands, the global model weights are aggregated when updates are received from all clients, and then sent back out to the clients.
        
        Returns: None
        """
        
        #process the request based on the command
        cmd = req.get("cmd")

        if cmd == "register":
            #register a new user or welcome an existing user
            user = req.get("user")
            if not user:
                conn.sendall(b'{"status":"error","msg":"no user"}\n')
                return
            #check if the user is already registered
            with state_lock:
                if user in self.client_info:
                    conn.sendall(b'{"status":"ok","msg":"welcome","portfolio":' + json.dumps(self.client_info[user]).encode() + b'}\n')
                    return
                
                #new clients get a fresh portfolio - everyone starts with 10 shares 
                self.client_info[user] = {}
                fresh = load_json(self.stock_file, {})
                #initialize the portfolio with 10 shares of each stock
                new_portfolio = {
                    sym: [ 10,     #10 shares
                       price,      #cost_basis = current price
                       10,          #realized P&L
                       10 ]         #unrealized P&L
                    for sym, price in fresh.items()}
                #save the new portfolio to the client_info
                self.client_info[user] = new_portfolio
                save_json(clientfile, self.client_info)
            conn.sendall(b'{"status":"ok","msg":"registered"}\n')
            return

        if cmd == "get_portfolio":
            user = req.get("user")
            #get the user's portfolio
            if not user:
                conn.sendall(b'{"status":"error","msg":"user required"}\n')
                return

            #load the stock prices from the file
            fresh = load_json(stockfile, {})
            with state_lock:
                #update the global stock_info variable with the fresh data
                global stock_info
                stock_info = fresh

                #update the user's portfolio with the latest stock prices
                port = self.client_info.setdefault(user, {})
                for sym, price in stock_info.items():
                    #if the symbol is not in the portfolio, add it with 0 shares
                    if sym not in port:
                        port[sym] = [0, price, 0, 0]

                #update the portfolio with the latest stock prices and other info
                for sym, raw in list(port.items()):
                    shares, basis, _, _ = raw
                    current_price = stock_info.get(sym, basis)
                    unreal = shares * (current_price - basis)
                    pct    = ((current_price - basis) / basis) * 100 if basis else 0.0 
                    port[sym] = [
                        shares,
                        round(current_price, 2),
                        round(pct, 2),
                        round(unreal, 2)]

                #save the updated portfolio to the client_info
                save_json(clientfile, self.client_info)
                updated = port

            #send the updated portfolio to the client
            resp = {"status": "ok", "portfolio": updated}
            conn.sendall((json.dumps(resp) + "\n").encode())
            return

        if cmd == "list_symbols":
            #list all available stock symbols
            with state_lock:
                syms = list(self.stock_info.keys())
            conn.sendall((json.dumps({"status":"ok","symbols":syms}) + "\n").encode())
            return

        if cmd in ("buy","sell"):
            #get the user, symbol, and quantity from the request
            user, sym, qty = req.get("user"), req.get("symbol"), req.get("qty")
            if None in (user, sym, qty):
                conn.sendall(b'{"status":"error","msg":"user,symbol,qty required"}\n')
                return
            with state_lock:
                #update the global stock_info variable with the fresh data
                port = self.client_info.setdefault(user, {})
                raw = port.get(sym, [0,0,0,0])
                entry = raw[:]
                shares, basis, realized, _ = entry
                current_price = self.stock_info.get(sym, basis)

                if cmd == "buy":
                    #buy shares
                    new_shares = shares + qty
                    #impose hard limit on the number of shares that can be bought
                    if new_shares > 200:
                        conn.sendall(b'{"status":"error","msg":"share limit exceeded"}\n')
                        return
                    entry[0] = new_shares
                    entry[1] = current_price

                else:
                    #sell shares
                    new_shares = shares - qty
                    #if we don't have enough shares, throw up an error so we can't sell 
                    if new_shares < 0:
                        conn.sendall(b'{"status":"error","msg":"not enough shares"}\n')
                        return
                    
                    #calculate the realized gain/loss
                    gain = qty * (current_price - basis)
                    entry[2] = round(realized + gain, 2)
                    entry[0] = new_shares
                    entry[1] = current_price
                #if we sold all the shares, remove the symbol from the portfolio
                if new_shares == 0:
                    port.pop(sym, None)
                else:
                    #calculate the unrealized gain/loss
                    unreal = new_shares * (current_price - entry[1])
                    pct    = ((current_price - entry[1]) / entry[1]) * 100
                    entry[3] = round(unreal, 2)
                    entry[1] = current_price
                port[sym] = entry
                save_json(clientfile, self.client_info)
                updated = port
            conn.sendall((json.dumps({"status":"ok","msg":"portfolio updated","portfolio":updated}) + "\n").encode())
            return

        #federated learning commands 
        if cmd == "get_global_model":
            #get the global model weights
            print(f"[SERVER] handing out global_weights = {self.global_weights}")
            conn.sendall((json.dumps({"status":"ok","weights": self.global_weights}) + "\n").encode())
            return

        if cmd == "update_model":
            #update the global model with weights from the client
            user = req.get("user")
            weights = req.get("weights")
            print(f"weights recieved from the client: ", weights)
            if user is None or weights is None:
                conn.sendall(b'{"status":"error","msg":"user,weights required"}\n')
                return
            self.updates[user] = weights
            conn.sendall(b'{"status":"ok","msg":"model received"}\n')
            # aggregate when all clients have sent updates
            K = len(self.updates)
            self.global_weights = [
                sum(w[i] for w in self.updates.values())/K
                for i in range(len(self.global_weights))]
            self.updates.clear()
            print("[SERVER]: aggregated global_weights:", self.global_weights)
            return

        else:
            conn.sendall(b'{"status":"error","msg":"unknown cmd"}\n')


    def handle_client(self, conn, addr):
        """
        Handles communication with a connected client.
        This function continuously receives data from the client, processes it line by line,
        and sends appropriate responses. It expects JSON-formatted requests from the client
        and processes them using the `process_request` method. If invalid JSON is received,
        an error message is sent back to the client.

        Args: conn (socket.socket): The socket object representing the client connection.
            addr (tuple): The address of the connected client (IP address and port).

        Raises: None

        NOTES:
            - The function reads data in chunks of size `BUFFER_SIZE`.
            - Each request from the client must end with a newline character (`\n`).
            - The connection is closed when the client disconnects or an error occurs.
        """

        buffer = ""
        try:
            while True:
                #receive data from the client
                data = conn.recv(self.BUFFER_SIZE).decode()
                if not data:
                    break
                #process the data line by line
                buffer += data
                while "\n" in buffer:
                    #split the buffer into lines and process each line again
                    line, buffer = buffer.split("\n",1)
                    if not line.strip():
                        continue
                    try:
                        #parse the line as JSON
                        req = json.loads(line)
                    except json.JSONDecodeError:
                        conn.sendall(b'{"status":"error","msg":"bad json"}\n')
                    else:
                        #process the request
                        self.process_request(req, conn,
                            self.stock_file, self.currency_file, self.clients_file)
        finally:
            #close the connection when done
            conn.close()


    def reload_prices(self):
        """
        Periodically reloads stock prices from a JSON file and updates the global stock information.
        Updates the global `stock_info` variable with the latest stock data and schedules itself to run again after `UPDATE_INTERVAL` seconds.

        This function reads the stock data from the specified JSON file, updates the global `stock_info`
        variable within a thread-safe context using a lock, and schedules itself to run again after
        a defined interval.

        Args: None 
        Returns: None

        Attributes: UPDATE_INTERVAL (int): The interval in seconds at which the stock prices are reloaded.

        NOTES: This function assumes that `self.stock_file` contains the path to the JSON file with stock data,
            and that `self.scheduler` is an instance of a scheduler capable of scheduling tasks.
        """

        #reload stock prices from the file
        UPDATE_INTERVAL = 5
        fresh = load_json(self.stock_file, {})
        #update the global stock_info variable with the fresh data
        with state_lock:
            global stock_info
            stock_info = fresh
        self.scheduler.enter(UPDATE_INTERVAL, 1, self.reload_prices)


    def serve_forever(self):
        """
        Starts the server and handles incoming client connections indefinitely.
        This method initializes the server socket, binds it to the specified host and port,
        and listens for incoming connections. It also starts a background thread to run
        scheduled tasks using a scheduler. For each client connection, a new thread is
        spawned to handle the client.

        The server state is loaded before starting and saved when the server shuts down.
        This method runs indefinitely until interrupted or terminated.

        We:
            -Load the server state.
            -Create and configure a socket for the server.
            -Bind the socket to the specified host and port.
            -Start listening for incoming connections.
            -Schedule periodic tasks using the scheduler.
            -Accept and handle client connections in separate threads.
            -Save the server state and close the socket when shutting down.

        Args: None 
        Returns: None

        Raises: Any exceptions raised during socket operations or client handling
            will propagate unless explicitly handled elsewhere.

        """

        #load the server state
        self.load_state()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind((self.host, self.port))
        srv.listen()
        print(f"Server listening on {self.host}:{self.port}")
        #schedule the reload_prices function to run every interval
        self.scheduler.enter(0, 1, self.reload_prices)
        threading.Thread(target=self.scheduler.run, daemon=True).start()
        try:
            #accept incoming connections
            while True:
                conn, addr = srv.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        finally:
            #save the server state and close the socket
            self.save_state()
            srv.close()


def load_json(path, default):
    """
    Loads a JSON object from a file if it exists, otherwise returns a default value.

    Args: path (str): The file path to the JSON file.
        default (Any): The default value to return if the file does not exist.

    Returns: Any: The loaded JSON object if the file exists, otherwise the default value.
    """

    #load json from file if it exists, otherwise return default
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    """
    This function writes the JSON data to a temporary file first and then
    replaces the original file with the temporary file. This ensures that
    the file is not corrupted if the program crashes during the write process.

    Args: path (str): The file path where the JSON data should be saved.
        data (dict): The dictionary data to be serialized and saved as JSON.

    Returns: None
    Raises: OSError: If there is an issue writing to the file or replacing it.
        TypeError: If the data provided is not serializable to JSON.
    """

    #write to a temporary file and then replace the original file
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


if __name__ == "__main__":
    """Main entry point for TradingServer."""

    server = TradingServer(
        #host the server on harvard public wifi bc that's the only way we can get past encryption
        host='10.253.128.85', port=50004,
        stock_file='stocks.txt', currency_file='currency.txt', clients_file='clients.txt')
    server.serve_forever()

