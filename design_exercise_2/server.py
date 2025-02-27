import socket
import threading
import queue

#global dict to keep track of active clients.
#client is stored as: username -> {'conn': socket, 'queue': Queue()}
active_clients = {}

def SendMessage(sender, recipient, message):
    """
    Sends a message from sender to recipient.
    If the recipient is online, places the message in their queue.
    Returns a status string.
    """
    if recipient in active_clients:
        active_clients[recipient]['queue'].put((sender, message))
        print(f"{sender} is messaging {recipient}.")
        print(f"Message from {sender} to {recipient} delivered.")
        return "Message delivered successfully."
    else:
        return "Recipient not connected."


def ReceiveMessages(username):
    """
    Continuously sends queued messages to the client.
    This function runs in its own thread for each connected client.
    """

    client_queue = active_clients[username]['queue']
    conn = active_clients[username]['conn']
    while True:
        try:
            sender, msg = client_queue.get()#timeout here? 
            #message formatting
            formatted_msg = f"{sender}: {msg}\n"
            conn.sendall(formatted_msg.encode('utf-8'))
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Error sending message to {username}: {e}")
            break

def handle_client(conn, addr):
    """
    Handles an individual client connection.
    First receives the username, then starts a background thread
    for sending queued messages (ReceiveMessages) while processing
    incoming messages from the client in a loop.
    """

    print(f"New connection from {addr}")
    username = None
    try:
        #the first message from the client must be the username.
        username = conn.recv(1024).decode('utf-8').strip()
        if not username:
            conn.close()
            return

        #add the client to active_clients with its own message queue and start a thread for continuous messaging
        active_clients[username] = {'conn': conn, 'queue': queue.Queue()}
        print(f"Client {username} has connected.")
        threading.Thread(target=ReceiveMessages, args=(username,), daemon=True).start()

        #process messages in real time
        while True:
            data = conn.recv(1024)
            if not data:
                break  
            #messages must be in the format "recipient::message"
            message = data.decode('utf-8').strip()
            if "::" not in message:
                conn.sendall("Invalid message format. Use recipient::message\n".encode('utf-8'))
                continue
            recipient, msg = message.split("::", 1)
            response = SendMessage(username, recipient, msg)
            if response != "Message delivered successfully.":
                conn.sendall((response + "\n").encode('utf-8'))
    
    except Exception as e:
        print(f"Error with client {addr}: {e}")
    
    finally:
        if username and username in active_clients:
            del active_clients[username]
        conn.close()
        print(f"Connection from {addr} closed.")


def start_server():
    host = "0.0.0.0"
    port = 50051
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()
    print(f"Server listening on port {port}")

    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()
