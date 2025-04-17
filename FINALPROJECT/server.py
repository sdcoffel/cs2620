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

# ————— In‑memory state —————
stock_info    = {}   # loaded from STOCK_FILE
currency_info = {}   # loaded from CURRENCY_FILE
client_info   = {}   # loaded from CLIENTS_FILE



def handle_client(conn, addr):
    print(f"[+] Connection from {addr}")
    username = None
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
                    continue
                #process_request(req, conn, STOCK_FILE, CURRENCY_FILE, CLIENTS_FILE)

                cmd = req.get("cmd")
                if cmd == "register":
                    user = req.get("user")
                    if not user:
                        conn.sendall(b'{"status":"error","msg":"no user"}\n')
                        continue
                    with clients_lock:
                        if user in clients:
                            conn.sendall(b'{"status":"error","msg":"username taken"}\n')
                            continue
                        clients[user] = conn
                    username = user
                    conn.sendall(b'{"status":"ok","msg":"registered"}\n')

                elif cmd == "send":
                    if username is None:
                        conn.sendall(b'{"status":"error","msg":"register first"}\n')
                        continue
                    target = req.get("to")
                    msg    = req.get("msg")
                    if not target or msg is None:
                        conn.sendall(b'{"status":"error","msg":"to/msg required"}\n')
                        continue

                # elif cmd == "get_users":
                #     with state_lock:
                #         users = list(client_info.keys())
                #     conn.sendall((json.dumps({"status":"ok","users":users})+"\n").encode())


                    with clients_lock:
                        dest = clients.get(target)
                    if dest:
                        payload = {"from": username, "msg": msg}
                        dest.sendall((json.dumps(payload) + "\n").encode())
                        conn.sendall(b'{"status":"ok","msg":"sent"}\n')
                    else:
                        conn.sendall(b'{"status":"error","msg":"user not online"}\n')

                else:
                    conn.sendall(b'{"status":"error","msg":"unknown cmd"}\n')

    finally:
        # cleanup on disconnect
        print(f"[-] Disconnected {addr}")
        if username:
            with clients_lock:
                del clients[username]
        conn.close()

def main():
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
        srv.close()

if __name__ == "__main__":
    main()

