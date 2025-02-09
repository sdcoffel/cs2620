#TODO: 
# - if i start the client before the server, the connection is refused. i should have a mechanism that continuously polls the server until it's online
# when i end the chat, i get [Errno 9] Bad file descriptor. this just means that its no longer connected to the server. i should have a way of exiting gracefully so i don't get that scary message

import socket
import threading
import hashlib
import re


def hash_password(password):
    """Hash a password for storing. This uses hashlib to hash the password and then send it over the network."""
    return hashlib.sha256(password.encode()).hexdigest()


def receive_messages(sock):
    """ This function is in charge of recieving messages that have been forwarded from the server. 

    Args: 
        sock (socket.socket()): Socket that the client is currently connected to the server with. 

    Returns: 
        Will return with an exception if the connection between the server and the client goes down. Else will continue until either the client or server
        terminates the connection.

    """
    try:
        while True:
            message = sock.recv(1024).decode('utf-8')
            if message:
                print("\rReceived: " + message + "\nYou: ", end="")
            else:
                print("\nServer closed the connection.")
                break

    except socket.error as e:
        if e.errno != 9:  # Suppress the "Bad file descriptor" error
            print(f"Error receiving data: {e}")

    except Exception as e:
        print(f"Error receiving data: {e}")
    finally:
        try:
            sock.close()
        except Exception as e:
            print(f"Failed to close the socket properly: {e}")



def send_messages(sock, username, recipient):
    """Sends messages along the socket to the server. If an empty message is typed, the user has the power to 
    terminate the connection when prompted. Different error handling mechanisms are at the bottom of the function. 
    The user can exit the chat by typing 'quit', change the intended recipient by typing 'change', or delete a message that was sent during that session by typing 'delete'.

    Args: 
        sock (socket.socket): Socket the client is currently connected with. 

    Continues until the connection is terminated, handles exceptions if the message cannot be sent.
    
    """
    
    try:
        while True:
            message = input("You: ")
            if message.lower() == 'quit':
                print("Ending connection...")
                break

            elif message.lower() == 'change':
                recipient = input("Enter the recipient's username: ")
                print(f"Now messaging {recipient}. Type 'quit' to end the session, 'change' to change the recipient, or 'delete' to delete any messages.")
                continue

            #for message deletion
            elif message.lower().startswith('delete'):
                sock.send(message.encode('utf-8'))
                continue

            elif message.lower() == 'logout':
                sock.send(message.encode('utf-8'))
                print("Logging out...")
                break
            

            full_message = f"{recipient}:{message}"
            sock.send(full_message.encode('utf-8'))


    except socket.error as e:
        if e.errno != 9: 
            print(f"Error sending message: {e}")

    except Exception as e:
        print(f"Some unexpected error {e} has occurred: Please contact system administrators Savanna and Ian")
    
    finally:
        try:
            sock.close()
            print("You have exited the chat.")
            
        except Exception as e:
            print(f"Failed to close the socket properly: {e}")



def handle_login(client_socket):
    """Handles the login process for the client. This prompts the user for their login data, and sends it to the server for credential validation.
    If the user has any pending messages, these are handled at login and displayed for the client to see in bunches of 10 messages. The client can request to see another 10 messages 
    at a time if they wish to see more. 
    """
    existing = input("Welcome to the chat app! Do you already have an account? (yes/no): ").strip().lower()

    logged_in = False #boolean that switches depending on if the user is logged in or not
    while not logged_in: 
        if existing == "no": 
            username = input("Please choose your new username: ").strip()

        elif existing == "yes":
            username = input("Please enter your username: ").strip() 

        password = input("Please enter your password: ").strip()
        hashed_password = hash_password(password) #hashes the password


        #send login credentials to the server
        credentials = f"{username},{hashed_password},{existing}"
        client_socket.send(credentials.encode('utf-8'))

        #wait for server confirmation to validate credentials
        server_message = client_socket.recv(1024).decode('utf-8')
        print(server_message)

        if "Success" in server_message or "Account created" in server_message:
            logged_in = True
        else: 
            pass

    #grab any pending messages
    pending_message_info = client_socket.recv(4096).decode('utf-8')
    print(pending_message_info)

    #if there are more than 10 messages, enter the loop and give the client the option to get more messages
    while True: 
        print("Type 'more to receive more messages or 'done' to continue. ")
        command = input(" | ").strip().lower()
        if command == "more": 
            client_socket.send(command.encode('utf-8'))
            more_messages = client_socket.recv(4096).decode('utf-8')

            if more_messages:
                print(more_messages)
            if "No more messages" in more_messages or "End of messages" in more_messages:
                print("Continuing to the chat...")
                break
        elif command == "done":
            print("Continuing to the chat...")
            break
        else: 
            print("Invalid input")

    print("Ready to go! Type 'logout' at any point in order to logout of the app.")
    return username, client_socket



def handle_action(client_socket, username):
    """Handles the action selection for the client. Clients can delete their account, list all accounts registered on the server, and begin messaging from here.
    If an action is not one of these keywords, prompt the client to try again.
    
    """
    action = input("Do you want to message, list users, or delete your account? (message/list/delete account): ").strip().lower()
    
    if action == "delete account":
        #this tells the server that we are going to delete the account
        client_socket.send("delete_account".encode('utf-8'))
        server_message = client_socket.recv(1024).decode('utf-8')
        print(server_message)

        if "You have unread messages" in server_message:
            confirmation = input("Are you sure you want to delete your account? (yes/no): ").strip().lower()
            client_socket.send(confirmation.encode('utf-8'))
            server_message = client_socket.recv(1024).decode('utf-8')
            print(server_message)
            if "Account deleted successfully" in server_message:
                return False
            else:
                return True
        else:
            return False
        
    
    elif action == "list": 
        client_socket.send("list_accounts".encode('utf-8'))
        server_message = client_socket.recv(1024).decode('utf-8')
        accounts = server_message.split('\n')
        print("List of users you can message: \n")
        print(server_message)

        while True:
            pattern = input("Enter a wildcard pattern to filter accounts (or 'all' to list all accounts): ").strip()
            if pattern.lower() == 'all':
                filtered_accounts = accounts
            else:
                filtered_accounts = [account for account in accounts if re.search(pattern, account)]
            
            if not filtered_accounts:
                print("No accounts match the given pattern.")
            else:
                for account in filtered_accounts:
                    print(account)
            
            more = input("Do you want to filter again? (yes/no): ").strip().lower()
            if more != 'yes':
                break
        
        return True
    
    elif action == "message":
        recipient = input("Who do you want to message? ")
        client_socket.send(recipient.encode('utf-8'))
        print(f"Now messaging {recipient}. Type 'quit' to end the session or 'change' to select another recipient.")
        threading.Thread(target=receive_messages, args=(client_socket,)).start()
        send_messages(client_socket, username, recipient)
        return False
    

    elif action == 'logout':
        client_socket.send(action.encode('utf-8'))
        print("Logging out...")
        False

    else:
        print("Invalid action. Please try again.")
        return True




def start_client():
    """Responsible for booting up the client and establishing the first connection to the server. Connects to the server on a localhost port. 

    """
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #server_port = 12345 #probably should not hardcode this, i have to change this every time and waldo will fail us
    try:
        client_socket.connect(('localhost', 12345))
        #client_socket.connect((server_ip, server_port)) #we should not hardcode this, i have to change this every time and waldo will fail us 
        print("Connected to the server.")

        username, client_socket = handle_login(client_socket)
        if not username:
            return

        while handle_action(client_socket, username):
            pass
    except Exception as e: 
        print(f"Unable to connect to the server :{e}")
    
    finally: 
        client_socket.close()

if __name__ == "__main__":
    # server_ip = input("Enter the server IP address: ")
    # start_client(server_ip)
    start_client()