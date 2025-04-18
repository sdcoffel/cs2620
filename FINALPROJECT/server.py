import socket
import threading
import json
from data_management import * 

HOST = '127.0.0.1'
PORT = 50005
BUFFER_SIZE = 1024

# each username gets assigned its own → socket
clients = {}
clients_lock = threading.Lock() #every client runs in its own thread


#state loading 
# ————— File paths —————
STOCK_FILE    = "stocks.txt"    # symbol → price/share
CURRENCY_FILE = "currency.txt"  # e.g. "USD->EUR" → rate
CLIENTS_FILE  = "clients.txt"   # client → { symbol: [shares, price/share, pct Δ, profit], … }

#working dicts that are loaded when the server boots up - for persistent storage 
stock_info    = {}   # loaded from STOCK_FILE
currency_info = {}   # loaded from CURRENCY_FILE
client_info   = {}   # loaded from CLIENTS_FILE


#parse messages coming in from the client and hand them off to the process_request helper function
def handle_client(conn, addr):
    buffer = ""
    try:
        while True:
            data = conn.recv(BUFFER_SIZE).decode()
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
                    process_request(req, conn, STOCK_FILE, CURRENCY_FILE, CLIENTS_FILE)
    finally:
        conn.close()


def main():
    #boot up the server - run each client in its own thread - could be useful bc all clients need access to the server's stock price info - but changes must be done atomically
    load_state(STOCK_FILE, CURRENCY_FILE, CLIENTS_FILE)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind((HOST, PORT))
    srv.listen()
    print(f"Server listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    finally:
        save_state(STOCK_FILE, CURRENCY_FILE, CLIENTS_FILE)
        print(f"Saving state...")
        srv.close()

if __name__ == "__main__":
    main()

