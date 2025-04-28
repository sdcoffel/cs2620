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
                
                #new clients get a fresh portfolio - everyone starts with 10 shares 
                self.client_info[user] = {}
                fresh = load_json(self.stock_file, {})
                new_portfolio = {
                    sym: [ 10,           # 10 shares
                       price,      # cost_basis = current price
                       10,          # realized P&L
                       10 ]         # unrealized P&L
                    for sym, price in fresh.items()
                }
                self.client_info[user] = new_portfolio
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

                port = self.client_info.setdefault(user, {})
                for sym, price in stock_info.items():
                    if sym not in port:
                        port[sym] = [0, price, 0, 0]


                for sym, raw in list(port.items()):
                    shares, basis, _, _ = raw
                    current_price = stock_info.get(sym, basis)
                    unreal = shares * (current_price - basis)
                    pct    = ((current_price - basis) / basis) * 100 if basis else 0.0

                    port[sym] = [
                        shares,
                        round(current_price, 2),
                        round(pct, 2),
                        round(unreal, 2)
                    ]

                save_json(clientfile, self.client_info)
                updated = port

            resp = {"status": "ok", "portfolio": updated}
            conn.sendall((json.dumps(resp) + "\n").encode())
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

        UPDATE_INTERVAL = 5
        fresh = load_json(self.stock_file, {})
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

        Steps:
        1. Load the server state.
        2. Create and configure a socket for the server.
        3. Bind the socket to the specified host and port.
        4. Start listening for incoming connections.
        5. Schedule periodic tasks using the scheduler.
        6. Accept and handle client connections in separate threads.
        7. Save the server state and close the socket when shutting down.

        Args: None 
        Returns: None
        
        NOTES: This method runs indefinitely until interrupted or terminated.

        Raises: Any exceptions raised during socket operations or client handling
            will propagate unless explicitly handled elsewhere.

        """

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
    """
    Loads a JSON object from a file if it exists, otherwise returns a default value.

    Args: path (str): The file path to the JSON file.
        default (Any): The default value to return if the file does not exist.

    Returns: Any: The loaded JSON object if the file exists, otherwise the default value.
    """

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

    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)



if __name__ == "__main__":
    """Main entry point for TradingServer."""

    server = TradingServer(
        host='localhost', port=50004,
        stock_file='stocks.txt', currency_file='currency.txt', clients_file='clients.txt')
    server.serve_forever()

