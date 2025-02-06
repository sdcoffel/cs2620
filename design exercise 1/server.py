#TODO:
# - figure out if pending messages are going to be stored here or not

import socket
import threading

active_clients = {}  #map of all active client usernames to their sockets. this is a universal map, which i like. i hesitate to hardcode anything though

def send_message(recipient, sender, message): 
    """This function will send a message to a specific client. We still have a synchronization bug, so the first message may not go through. Other than that, this is ok

    Args: 
        message: The incoming message from the client. 
        sender: The socket that belongs to the sender.
        recipient: The socket that belongs to the recipient. This is where message is being rerouted to

    If we (the server) cannot get a message through, throw an error but do not terminate the connection with the client

    """
    
    if recipient in active_clients and 'socket' in active_clients[recipient]:
        client_socket = active_clients[recipient]['socket'] #assign the desired recipient to a socket and save it in the active_clients dict

        try:
            full_message = f"from {sender}: {message}".encode('utf-8') 
            client_socket.send(full_message)
            print(f"Message from {sender} to {recipient} delivered.")

        except Exception as e:
            print(f"Failed to send message from {sender} to {recipient}: {e}")

    else:
        print(f"{recipient} not found. Message from {sender} not delivered.")



def client_handler(connection, address):
    """Establishes a connection with the client. 

    Args: 
        connection (socket.socket()): socket associated with the client
        address: IP address and port number of the client

    """

    try:
        print(f"Connected with {address}")
        username = connection.recv(1024).decode().strip() #the first message that the server gets is the username, so it knows which socket to assign the client to in active_clients
        connection.send("Username registered. Proceed.".encode('utf-8')) #verification for the client that they are online
        recipient = connection.recv(1024).decode().strip()

        if not username:
            raise ValueError("Username not provided")
        
        #server stores all associated details of the client in active_clients
        active_clients[username] = {
            "socket": connection,
            "recipient": recipient
        }
        print(f"{username} has connected and messaging {recipient}.")

        #update recipient dict only after client is registered
        recipient = connection.recv(1024).decode().strip()
        active_clients[username]["recipient"] = recipient
        print(f"{username} is messaging {recipient}.")

        while True:
            raw_message = connection.recv(1024)
            if not raw_message:
                break

            #more decoding
            decoded_message = raw_message.decode('utf-8')  
            recipient, msg = decoded_message.split(':', 1)  #split the message into recipient and message
            send_message(recipient, username, msg)

    except Exception as e:
        print(f"Errors with {username}: {e}")

    finally:
        connection.close()
        if username in active_clients:
            del active_clients[username]  #client gets removed from the active active_clients dict
        print(f"{username} has disconnected")



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
