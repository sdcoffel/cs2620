#TODO:
# - figure out if pending messages are going to be stored here or not
# - only send message to a specific client, not broadcasting the entire thing

import socket
import threading

clients = []  #list of all clients currently online

def broadcast_message(message, sender_socket): 
    """This function broadcasts a client's message to everyone else by forwarding via the server. We need to tweak this by username eventually.

    Args: 
        message: The incoming message from the client. 
        sender_socket: The socket that belongs to the sender.

        If the server cannot get a message through, throw an error but do not terminate the connection with the client

    """
    for client in clients:
        if client != sender_socket:
            try:
                client.send(message)
            except Exception as e: 
                print(f"Error sending message to {client.getpeername()}: {e}")
                continue


def client_handler(connection, address):
    """Establishes a connection with the client. 

    Args: 
        connection (socket.socket()): socket associated with the client
        address: IP address and port number of the client

    """
    print(f"Connected with {address}")
    clients.append(connection)  
    
    while True:
        message = connection.recv(1024)
        if not message:
            break
        broadcast_message(message, connection) #all clients except the sender recieve a broadcast - an area to fix 
        #instead of broadcast_message, i should tweak something here that will allow me to send to only one client. this requires knowing the accounts that are registered

def start_server():
    """Responsible for booting up the server. 
    
    This will run until the server encounters an exception or is manually shut off.

    """
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  #this line guarantees that we can reuse the same port over and over again without having to change the number
        server_socket.bind(('localhost', 12345))
        server_socket.listen()
        print("Server is listening...")

        while True:
            try:
                client_socket, addr = server_socket.accept()
                thread = threading.Thread(target=client_handler, args=(client_socket, addr)) #in order to have multiple clients, i might model each of them as a thread. results pending on if this is a smart move or not
                thread.start()
            except Exception as e: 
                print(f"Fatal error {e} with server")
    
    finally: #close the socket gracefully
        try: 
            server_socket.close()
        except Exception as e: 
            print(f"Failed to close server socket properly! : {e}")
         

if __name__ == "__main__":
    start_server()
