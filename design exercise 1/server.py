#TODO:
# - figure out if pending messages are going to be stored here or not

import socket
import threading
import bcrypt
from accounts import load_accounts, save_accounts, create_account, is_valid_account, delete_account, list_accounts


def send_message(recipient, sender, message): 
    """This function will send a message to a specific client. We still have a synchronization bug, so the first message may not go through. Other than that, this is ok

    Args: 
        message: The incoming message from the client. 
        sender: The socket that belongs to the sender.
        recipient: The socket that belongs to the recipient. This is where message is being rerouted to

    If we (the server) cannot get a message through, throw an error but do not terminate the connection with the client

    """
    
    #currently both have to be active for the message to be delievered. i need to tweak this so that the message can be delivered even if the recipient is not active
    if recipient in active_clients and 'socket' in active_clients[recipient]:
        client_socket = active_clients[recipient]['socket'] #assign the desired recipient to a socket and save it in the active_clients dict

        try:
            full_message = f"{sender}: {message}".encode('utf-8') 
            client_socket.send(full_message)
            print(f"Message from {sender} to {recipient} delivered.")

        except Exception as e:
            print(f"Failed to send message from {sender} to {recipient}: {e}")

    else:
        print(f"{recipient} not found. Message from {sender} not delivered.")



def client_handler(connection, address):
    """Establishes a connection with the client Prompts for login info, and prompts for the recipient of any messages. Clients who wish to make a new account, log in, or delete their accounts 
    will be able to do so here. 

    Args: 
        connection (socket.socket()): socket associated with the client
        address: IP address and port number of the client

    """

    try:
        print(f"Connected with {address}")
        #get login credentials from the client
        credentials = connection.recv(1024).decode().strip().split(',')
        username, password, existing = credentials[0], credentials[1], credentials[2]
        accounts = load_accounts(FILE_PATH)
        while True: 

            try: 
                if existing == "no":
                    if username in accounts:
                        connection.send("Username already exists. Please try again.".encode('utf-8')) #bug here i need to fix
                    else: 
                        create_account(username, password, FILE_PATH) #create_account does all the checking for us
                        connection.send("Account created! You are now logged in.".encode('utf-8'))
                        break

                elif existing == "yes":
                    #checks if the password is correctly authenticated
                    if username in accounts and password == accounts[username]['password']:
                        connection.send("Success! You are now logged in.".encode('utf-8'))
                        break
                    
                    else: 
                        connection.send("Invalid username/password. Please try again.".encode('utf-8'))
                        continue
            
            except ValueError as e: 
                connection.send(f"Account creation failed: {e}. Please try again".encode('utf-8'))
                continue

                 
        #update the active clients dictionary with the new username. this gets updated no matter what, so i am putting it outside the conditional
        active_clients[username] = {
            "socket": connection
        }
        
        print(f"{username} has connected.")



        while True:
            #read the incoming message
            raw_message = connection.recv(1024).decode().strip()
            if not raw_message:
                break

            #special commands, like delete and list 
            if raw_message.lower() == "delete_account":
                delete_account(username, FILE_PATH)
                print(f"Account deletion requested by user {username}")
                connection.send("Account deleted successfully.".encode('utf-8'))
                break

            elif raw_message.lower() == "list_accounts":
                print(f"List requested by user {username}")
                all_clients = list_accounts(FILE_PATH)
                connection.send(all_clients.encode('utf-8'))
                continue

            #all other messages
            if ':' in raw_message:
                recipient, msg = raw_message.split(':', 1)
                send_message(recipient, username, msg)
                
            else:
                #handle setting the recipient and tracking in the server
                recipient = raw_message
                if recipient in accounts:
                    active_clients[username]["recipient"] = recipient
                    print(f"{username} is messaging {recipient}.")
                else:
                    connection.send("Invalid recipient. Please enter a valid username.".encode('utf-8'))

        
  
    except Exception as e:
        print(f"Errors: {e}")

    finally:
        connection.close()
        if username in active_clients:
            del active_clients[username] 
        print(f"{username} has disconnected")



def start_server():
    """Responsible for booting up the server. 
    
    This will run until the server encounters an exception or is manually shut off.

    """
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  #this line guarantees that we can reuse the same port over and over again without having to change the number
        #server_socket.bind(('0.0.0.0', 12345)) #listen on all network interfaces. if we actually text, we uncomment this line
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
    
    finally: 
        try: 
            server_socket.close()
        except Exception as e: 
            print(f"Failed to close server socket properly! : {e}")
         

if __name__ == "__main__":
    FILE_PATH = "all_accounts_ever.txt"
    active_clients = {}  #map of all active client usernames to their sockets. this is a universal map, which i like. i hesitate to hardcode anything though
    start_server()




  
