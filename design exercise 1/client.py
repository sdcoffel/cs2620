#TODO: 
# - if i start the client before the server, the connection is refused. i should have a mechanism that continuously polls the server until it's online
import socket
import threading
import hashlib
import re

class Client:

    def __init__(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #this is probably why i get the initial error of not connecting
        self.username = None
        self.connected = False


    def close_connection(self):
        if self.client_socket:
            self.client_socket.close()
            print("Connection closed.")


    @staticmethod
    def hash_password(password):
        """Hash a password for storing. This uses hashlib to hash the password and then send it over the network."""
        return hashlib.sha256(password.encode()).hexdigest()


    def receive_messages(self):
        """ This function is in charge of recieving messages that have been forwarded from the server. 

        Args: 
            sock (socket.socket()): Socket that the client is currently connected to the server with. 

        Returns: 
            Will return with an exception if the connection between the server and the client goes down. Else will continue until either the client or server
            terminates the connection.

        """
        try:
            while True:
                message = self.client_socket.recv(1024).decode('utf-8')
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
                self.client_socket.close()
            except Exception as e:
                print(f"Failed to close the socket properly: {e}")



    def send_messages(self, recipient):
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
                    self.client_socket.send(message.encode('utf-8'))
                    continue

                elif message.lower() == 'logout':
                    self.client_socket.send(message.encode('utf-8'))
                    print("Logging out...")
                    break
                

                full_message = f"{recipient}:{message}"
                self.client_socket.send(full_message.encode('utf-8'))


        except socket.error as e:
            if e.errno != 9: 
                print(f"Error sending message: {e}")

        except Exception as e:
            print(f"Some unexpected error {e} has occurred: Please contact system administrators Savanna and Ian")
        
        finally:
            try:
                self.client_socket.close()
                print("You have exited the chat.")
                
            except Exception as e:
                print(f"Failed to close the socket properly: {e}")



    def handle_login(self):
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
            hashed_password = self.hash_password(password) #hashes the password


            #send login credentials to the server
            credentials = f"{username},{hashed_password},{existing}"
            self.client_socket.send(credentials.encode('utf-8'))

            #wait for server confirmation to validate credentials
            server_message = self.client_socket.recv(1024).decode('utf-8')
            print(server_message)

            if "Success" in server_message or "Account created" in server_message:
                logged_in = True
                self.username = username
                break
            else: 
                pass

        #grab any pending messages
        pending_message_info = self.client_socket.recv(4096).decode('utf-8')
        print(pending_message_info)

        #if there are more than 10 messages, enter the loop and give the client the option to get more messages
        while True: 
            print("Type 'more to receive more messages or 'done' to continue. ")
            command = input(" | ").strip().lower()
            if command == "more": 
                self.client_socket.send(command.encode('utf-8'))
                more_messages = self.client_socket.recv(4096).decode('utf-8')

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



    def handle_action(self):
        """Handles the action selection for the client. Clients can delete their account, list all accounts registered on the server, and begin messaging from here.
        If an action is not one of these keywords, prompt the client to try again.
        
        """
        action = input("Do you want to message, list users, or delete your account? (message/list/delete account): ").strip().lower()
        
        if action == "delete account":
            #this tells the server that we are going to delete the account
            self.client_socket.send("delete_account".encode('utf-8'))
            server_message = self.client_socket.recv(1024).decode('utf-8')
            print(server_message)

            if "You have unread messages" in server_message:
                confirmation = input("Are you sure you want to delete your account? (yes/no): ").strip().lower()
                self.client_socket.send(confirmation.encode('utf-8'))
                server_message = self.client_socket.recv(1024).decode('utf-8')
                print(server_message)
                if "Account deleted successfully" in server_message:
                    return False
                else:
                    return True
            else:
                return False
            
        
        elif action == "list": 
            self.client_socket.send("list_accounts".encode('utf-8'))
            server_message = self.client_socket.recv(1024).decode('utf-8')
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
            self.client_socket.send(recipient.encode('utf-8'))
            print(f"Now messaging {recipient}. Type 'quit' to end the session or 'change' to select another recipient.")
            threading.Thread(target=self.receive_messages).start()
            self.send_messages(recipient)
            return False
        

        elif action == 'logout':
            self.client_socket.send(action.encode('utf-8'))
            print("Logging out...")
            False

        else:
            print("Invalid action. Please try again.")
            return True




    def start_client(self, host, port):
        """Responsible for booting up the client and establishing the first connection to the server. Connects to the server on a localhost port. 

        """
        host = 'localhost'
        port = 12345 #do not hardcode these, have user supply them on the GUI side
        #self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #server_port = 12345 #probably should not hardcode this, i have to change this every time and waldo will fail us
        try:
            self.client_socket.connect((host, port))

            #this is for switching to LAN mode on harvard public wifi. ignore for now
            #client_socket.connect((server_ip, server_port)) #we should not hardcode this, i have to change this every time and waldo will fail us 
            self.connected = True
            print("Connected to the server.")
            
            #i will comment this out in the GUI fyi ian
            self.handle_login()
            while self.handle_action(): 
                pass

        except Exception as e: 
            print(f"Unable to connect to the server :{e}")
            self.connected = False
        
        finally: 
            self.client_socket.close()

