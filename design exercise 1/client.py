#TODO: 
# - if i start the client before the server, the connection is refused. i should have a mechanism that continuously polls the server until it's online
# when i end the chat, i get [Errno 9] Bad file descriptor. this just means that its no longer connected to the server. i should have a way of exiting gracefully so i don't get that scary message


import socket
import threading

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

def send_messages(sock):
    """Sends messages along the socket to the server. If an empty message is typed, the user has the power to 
    terminate the connection when prompted. Different error handling mechanisms are at the bottom of the function. 

    Args: 
        sock (socket.socket): Socket the client is currently connected with. 

    Continues until the connection is terminated, handles exceptions if the message cannot be sent.
    
    """
    try:
        while True:
            message = input("You: ")
            if not message:
                confirm = input("No message entered. Would you like to end the connection? (yes/no) ").strip().lower()
                if confirm == 'yes':
                    print("Ending connection...")
                    break
                elif confirm == 'no':
                    continue
                else:
                    print("Please type 'yes' or 'no'.")
                    continue

            sock.send(message.encode('utf-8'))

    except socket.error as e:
        print(f"Error sending message: {e}")
    except KeyboardInterrupt:
        print("You have exited the chat.")
    except Exception as e:
        print(f"Some unexpected error {e} has occurred: Please contact system administrators Savanna and Ian")
    finally:
        try:
            sock.close()
            print("Socket closed.")
        except Exception as e:
            print(f"Failed to close the socket properly: {e}")


def start_client():
    """Responsible for booting up the client and establishing the first connection to the server. 

    """
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 12345)) #we should not hardcode this, i have to change this every time and waldo will fail us 

    threading.Thread(target=receive_messages, args=(client_socket,)).start()
    send_messages(client_socket)

if __name__ == "__main__":
    #currently, i broadcast messages to everybody except the source client. i want to make this so that i can specify by username who to send a message to. that requires knowing usernames
    start_client()
