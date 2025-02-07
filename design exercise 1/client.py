#TODO: 
# - if i start the client before the server, the connection is refused. i should have a mechanism that continuously polls the server until it's online
# when i end the chat, i get [Errno 9] Bad file descriptor. this just means that its no longer connected to the server. i should have a way of exiting gracefully so i don't get that scary message
#fix the hashing and do it client side. rn i can't get into my own account

import socket
import threading
import bcrypt

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
                print(f"Now messaging {recipient}. Type 'quit' to end the session.")
                continue

            full_message = f"{recipient}:{message}"
            sock.send(full_message.encode('utf-8'))


    except socket.error as e:
        print(f"Error sending message: {e}")

    except Exception as e:
        print(f"Some unexpected error {e} has occurred: Please contact system administrators Savanna and Ian")
    
    finally:
        try:
            sock.close()
            print("You have exited the chat.")
            
        except Exception as e:
            print(f"Failed to close the socket properly: {e}")


def start_client():
    """Responsible for booting up the client and establishing the first connection to the server. 

    """
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #server_port = 12345 #probably should not hardcode this, i have to change this every time and waldo will fail us
    try:
        client_socket.connect(('localhost', 12345))
        #client_socket.connect((server_ip, server_port)) #we should not hardcode this, i have to change this every time and waldo will fail us 
        print("Connected to the server.")

       #get login information from the user
        existing = input("Welcome to the chat app! Do you already have an account? (yes/no): ").strip().lower()
        username = " " # to be filled in by the user

        if existing == "no":
            username = input("Please choose your username: ").strip()
            password = input("Please choose your password: ").strip()

        if existing == "yes":
            username = input("Please enter your username: ").strip()
            password = input("Please enter your password: ").strip()

        #hash all passwords before sending them to the server
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()) 

        #send login credentials to the server
        credentials = f"{username},{hashed_password},{existing}"
        client_socket.send(credentials.encode('utf-8'))

        #wait for server confirmation to validate credentials
        server_message = client_socket.recv(1024).decode('utf-8')
        print(server_message)

        if "Invalid username/password" in server_message:
            client_socket.close()
            return
        


        recipient = input("Who do you want to message? ")
        client_socket.send(recipient.encode('utf-8'))
        print(f"Now messaging {recipient}. Type 'quit' to end the session or 'change' to select another recipient.")


        threading.Thread(target=receive_messages, args=(client_socket,)).start()
        send_messages(client_socket, username, recipient)
    
    except Exception as e: 
        print(f"Unable to connect to the server :{e}")
    
    finally: 
        client_socket.close()

if __name__ == "__main__":
    # server_ip = input("Enter the server IP address: ")
    # start_client(server_ip)
    start_client()