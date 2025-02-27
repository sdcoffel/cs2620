import socket
import threading

def receive_messages(sock):
    """
    Continuously receives messages from the server and prints them.
    """
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                print("Server disconnected.")
                break
            print("\n" + data.decode('utf-8').strip() + "\nYou: ", end="", flush=True)
        except Exception as e:
            print("Error receiving message:", e)
            break

def start_client():
    host = input("Enter server host: ")
    port = int(input("Enter server port: "))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    #the username is the first message - send it to the server
    username = input("Enter your username: ").strip()
    sock.send(username.encode('utf-8'))
    print(f"Connected to the server as {username}.")

    #set recipient and start thread
    default_recipient = input("Enter recipient: ").strip()
    print(f"Default recipient set to {default_recipient}")
    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    #main processing loop
    while True:
        #if a default recipient is set, use it; otherwise, prompt for recipient.
        if default_recipient:
            message = input("You: ")
            if not message:
                continue
            msg_to_send = f"{default_recipient}::{message}"
        else:
            recipient = input("Enter recipient: ").strip()
            message = input("Enter message: ")
            msg_to_send = f"{recipient}::{message}"

        try:
            sock.send(msg_to_send.encode('utf-8'))
        except Exception as e:
            print("Error sending message:", e)
            break

if __name__ == "__main__":
    start_client()
