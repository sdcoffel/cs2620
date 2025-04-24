import socket
import threading
import json
import sys
import argparse


class TradingCLient: 

    def init(self, host: str, port: int):
        self.host = host
        self.port = port
        self.buffer_size = 1024
        self.sock = None
        self.username = None
        self.portfolio = {}


    def listen(self):
        global portfolio
        buffer = ""
        while True:
            data = self.sock.recv(self.buffer_size).decode()
            if not data:
                print("\n[-] Server closed connection.")
                self.sock.close()
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
                            self.print_portfolio()
                    else:
                        print(f"\n[Server] Unknown response: {msg}")
                # redraw prompt
                print("> ", end="", flush=True)


    def compute_net_profit(self, portfolio):
        """
        Given a portfolio dict of the form:
          { symbol: [shares, cost_basis, realized_profit, unrealized_profit, total_profit], … }
        returns a tuple (net_realized, net_unrealized, net_total)
        """
        net_realized   = 0.0
        net_unrealized = 0.0

        for entry in portfolio.values():
            # unpack: [shares, cost_basis, realized, unrealized]
            _, _, realized, unrealized = entry
            net_realized   = realized        # or realized, if you want just this session’s gains
            net_unrealized += unrealized

        net_total = net_realized + net_unrealized
        return net_total


    def print_portfolio(self):
        if not portfolio:
            print("No holdings yet.")
        else:
            print("Your portfolio:")

            for sym, info in portfolio.items():
                shares, price, pct, profit = info
                print(f"    • {sym}: {shares} @ ${price:.2f}   Δ {pct:+.1f}%   P&L ${profit:.2f}")

        net_all = self.compute_net_profit(portfolio)
        print("Overall net profit:    $", round(net_all,   2))



    def main(self):
        print(f"Establishing connection...")
        #connect to the server
        self.sock = socket.create_connection((self.host, self.port))
        username = input("Who are you?: ").strip()
        self.sock.sendall((json.dumps({"cmd":"register","user":username}) + "\n").encode())

        #wait until the server acknowledges the connection
        ack = self.sock.recv(self.buffer_size).decode().split("\n",1)[0]
        resp = json.loads(ack)
        if resp.get("status") != "ok":
            print("Registration failed:", resp.get("msg"))
            return

        #grab the user's initial portfolio - for now, we all start with a blank, unpopulated portfolio
        self.sock.sendall((json.dumps({"cmd":"get_portfolio","user":username}) + "\n").encode())

        print(
          "Commands:\n"
          "  portfolio           show your holdings\n"
          "  buy SYMBOL QTY      buy shares\n"
          "  sell SYMBOL QTY     sell shares\n"
          "  quit                exit\n"
        )

        #background listener thread
        threading.Thread(target=self.listen, daemon=True).start()

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
                self.sock.sendall((json.dumps({"cmd":"get_portfolio","user":username}) + "\n").encode())

            elif cmd in ("buy", "sell"):
                if len(parts) != 3 or not parts[2].isdigit():
                    print("Usage: buy SYMBOL QTY")
                    continue
                sym, qty = parts[1].upper(), int(parts[2])
                req = {"cmd": cmd, "user": username, "symbol": sym, "qty": qty}
                self.sock.sendall((json.dumps(req) + "\n").encode())

            else:
                print("Unknown command. Try: portfolio, buy SYMBOL QTY, sell SYMBOL QTY, or quit")

        self.sock.close()
        print("Ending trading session...")


if __name__ == "__main__":

    #change these from being hardcoded please
    HOST = '10.253.137.44' #don't hardcode this please for the love of god
    PORT = 50004
    client = TradingCLient()
    client.init(HOST, PORT)
    client.main()

