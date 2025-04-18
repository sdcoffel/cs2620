import socket
import threading
import json
import sys

HOST = '127.0.0.1'
PORT = 50005
BUFFER_SIZE = 1024

#local cache of the client's portfolio: { symbol: [shares, price, pct Δ, profit], … }
portfolio = {}

def listen(sock):
    global portfolio
    buffer = ""
    while True:
        data = sock.recv(BUFFER_SIZE).decode()
        if not data:
            print("\n[-] Server closed connection.")
            sock.close()
            sys.exit(0)
        buffer += data
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print(f"\n[!] Malformed from server: {line}")
            else:
                #server acknowledgements & portfolio updates
                if msg.get("status"):
                    print(f"\n[Server] {msg['status']}: {msg.get('msg','')}")
                    if msg.get("portfolio") is not None:
                        #global portfolio
                        portfolio = msg["portfolio"]
                        print_portfolio()
                else:
                    print(f"\n[Server] Unknown response: {msg}")
            # redraw prompt
            print("> ", end="", flush=True)

def print_portfolio():
    if not portfolio:
        print("No holdings yet.")
    else:
        print("Your portfolio:")
        for sym, info in portfolio.items():
            shares, price, pct, profit = info
            print(f"    • {sym}: {shares} @ ${price:.2f}   Δ {pct:+.1f}%   P&L ${profit:.2f}")

def main():
    #connect to the server
    sock = socket.create_connection((HOST, PORT))
    username = input("Who are you?: ").strip()
    sock.sendall((json.dumps({"cmd":"register","user":username}) + "\n").encode())

    #wait until the server acknowledges the connection
    ack = sock.recv(BUFFER_SIZE).decode().split("\n",1)[0]
    resp = json.loads(ack)
    if resp.get("status") != "ok":
        print("Registration failed:", resp.get("msg"))
        return

    #grab the user's initial portfolio - for now, we all start with a blank, unpopulated portfolio
    sock.sendall((json.dumps({"cmd":"get_portfolio","user":username}) + "\n").encode())

    print(
      "Commands:\n"
      "  portfolio           show your holdings\n"
      "  buy SYMBOL QTY      buy shares\n"
      "  sell SYMBOL QTY     sell shares\n"
      "  quit                exit\n"
    )

    #background listener thread
    threading.Thread(target=listen, args=(sock,), daemon=True).start()

    #input loop for commands
    while True:
        line = input("> ").strip()
        if not line:
            continue
        if line.lower() in ("quit", "exit"):
            break

        parts = line.split()
        cmd = parts[0].lower()

        if cmd == "portfolio":
            sock.sendall((json.dumps({"cmd":"get_portfolio","user":username}) + "\n").encode())

        elif cmd in ("buy", "sell"):
            if len(parts) != 3 or not parts[2].isdigit():
                print("Usage: buy SYMBOL QTY")
                continue
            sym, qty = parts[1].upper(), int(parts[2])
            req = {"cmd": cmd, "user": username, "symbol": sym, "qty": qty}
            sock.sendall((json.dumps(req) + "\n").encode())

        else:
            print("Unknown command. Try: portfolio, buy SYMBOL QTY, sell SYMBOL QTY, or quit")

    sock.close()
    print("Ending trading session...")


if __name__ == "__main__":
    main()
