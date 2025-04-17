import socket
import threading
import json #we're gonna use json for this bc its standardized 
import sys

HOST = '127.0.0.1'
PORT = 50005
BUFFER_SIZE = 1024 #tweakable, but 1024 is a good default and its what we've been doing so far

def listen(sock):
    buffer = ""
    while True:
        data = sock.recv(BUFFER_SIZE).decode()
        if not data:
            print("\n[-] Server closed connection.")
            # if the server goes away, make sure the prompt loop will exit
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
                print(f"\n[!] Received malformed: {line}")
            else:
                #incoming data
                if "from" in msg and "msg" in msg:
                    print(f"\n[{msg['from']}] {msg['msg']}")
                #server responses - makes sure that the server recieved the client's info
                elif msg.get("status"):
                    print(f"\n[Server] {msg['status']}: {msg.get('msg','')}")
                else:
                    print(f"\n[Server] {msg}")
            # redraw prompt immediately after any incoming text
            print("> ", end="", flush=True)

def main():
    sock = socket.create_connection((HOST, PORT))
    username = input("Who are you?: ").strip()

    #username registration with the server - this is the first thing that happens on startup 
    sock.sendall((json.dumps({"cmd":"register","user":username}) + "\n").encode())
    #wait for ack synchronously (just once)
    ack = sock.recv(BUFFER_SIZE).decode().split("\n",1)[0]
    resp = json.loads(ack)
    if resp.get("status") != "ok":
        print("Registration failed:", resp.get("msg"))
        return

    print("You're in! Type `/username message` to message a specific user, or `quit` to exit.")

    # start background listener - same idea as DE1
    threading.Thread(target=listen, args=(sock,), daemon=True).start()

    #main loop for sending/recieving messages 
    while True:
        #i don't want to block the reciever and have to type enter every time. you could change this if you wanted to, but i personally wouldn't 
        line = input("> ").strip()
        if line.lower() in ("quit", "exit"):
            break

        if not line.startswith("/"):
            print("Incorrect format: use /username message")
            continue

        try:
            to, msg = line[1:].split(" ", 1)
        except ValueError:
            print("Incorrect format: use /username message")
            continue

        req = {"cmd":"send", "to":to, "msg":msg}
        sock.sendall((json.dumps(req) + "\n").encode())

    sock.close()
    print("Disconnected.")

if __name__ == "__main__":
    main()
