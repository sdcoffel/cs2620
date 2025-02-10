#TODO: 
# - if i start the client before the server, the connection is refused. i should have a mechanism that continuously polls the server until it's online
import socket
import threading
import hashlib
import re

class Client:

    def __init__(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
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
        
        message = self.client_socket.recv(1024).decode('utf-8')
        if message:
            print("\rReceived: " + message + "\nYou: ", end="")
        else:
            print("\nServer closed the connection.")
        
        return message #sends recieved message to GUI

    

    def send_messages(self, recipient, message):
        """Sends messages along the socket to the server. If an empty message is typed, the user has the power to 
        terminate the connection when prompted. Different error handling mechanisms are at the bottom of the function. 
        The user can exit the chat by typing 'quit', change the intended recipient by typing 'change', or delete a message that was sent during that session by typing 'delete'.

        Args: 
            sock (socket.socket): Socket the client is currently connected with. 

        Continues until the connection is terminated, handles exceptions if the message cannot be sent.
        
        """
        
        #try:


                # #for message deletion
                # elif message.lower().startswith('delete'):
                #     self.client_socket.send(message.encode('utf-8'))
                #     continue

                

        full_message = f"{recipient}:{message}"
        self.client_socket.send(full_message.encode('utf-8'))



    def handle_login(self, username, password, existing):
        """Handles the login process for the client. This prompts the user for their login data, and sends it to the server for credential validation.
        If the user has any pending messages, these are handled at login and displayed for the client to see in bunches of 10 messages. The client can request to see another 10 messages 
        at a time if they wish to see more. 
        """

        hashed_password = self.hash_password(password) #hashes the password


        #send login credentials to the server
        credentials = f"{username},{hashed_password},{existing}"
        self.client_socket.send(credentials.encode('utf-8'))
        print("Sent off credentials")

        #wait for server confirmation to validate credentials
        server_message = self.client_socket.recv(1024).decode('utf-8')
        print("Server message recieved")
        print(server_message)

        self.username = username
        return server_message



    def get_pending_messages(self):
        #grab any pending messages
        pending_message_info = self.client_socket.recv(4096).decode('utf-8')
        return pending_message_info


    def grab_more_messages(self):
        #should still have the 10 message limit
        self.client_socket.send("more".encode('utf-8'))
        more_messages = self.client_socket.recv(4096).decode('utf-8')
                
        return more_messages
    

 
    def delete_account(self):

    #if action == "delete account":
        #this tells the server that we are going to delete the account
        self.client_socket.send("delete_account".encode('utf-8'))
        server_message = self.client_socket.recv(1024).decode('utf-8')
        print(server_message)
        return server_message

        # if "You have unread messages" in server_message:
        #     confirmation = input("Are you sure you want to delete your account? (yes/no): ").strip().lower()
        #     self.client_socket.send(confirmation.encode('utf-8'))
        #     server_message = self.client_socket.recv(1024).decode('utf-8')
        #     print(server_message)
        #     if "Account deleted successfully" in server_message:
        #         return False
        #     else:
        #         return True
        # else:
        #     return False
            

    def confirm_deletion(self, server_message, confirmation): #confirmation either yes or no 
        if "You have unread messages" in server_message:
            confirmation = confirmation
            #confirmation = input("Are you sure you want to delete your account? (yes/no): ").strip().lower()
            self.client_socket.send(confirmation.encode('utf-8'))
            server_message = self.client_socket.recv(1024).decode('utf-8')
            #print(server_message)
            return server_message
            # if "Account deleted successfully" in server_message:
            #     return server_message
            # else:
            #     return server_message
        else:
            return False
        
        
    def list_accounts(self):

        #elif action == "list": 
        self.client_socket.send("list_accounts".encode('utf-8'))
        server_message = self.client_socket.recv(1024).decode('utf-8')
        accounts = server_message.split('\n')
        return accounts


    def wildcard(self, pattern, accounts):
        if pattern.lower() == 'all':
            filtered_accounts = accounts
        else:
            filtered_accounts = [account for account in accounts if re.search(pattern, account)]
        
        if not filtered_accounts:
                return ("No accounts match the given pattern.")
        
        return filtered_accounts
        
        
    def set_recipient(self, recipient):
        self.client_socket.send(recipient.encode('utf-8'))




    def start_client(self, host, port):
        """Responsible for booting up the client and establishing the first connection to the server. Connects to the server on a localhost port. 

        """
        
        self.client_socket.connect((host, port))

        #this is for switching to LAN mode on harvard public wifi. ignore for now
        #client_socket.connect((server_ip, server_port)) #we should not hardcode this, i have to change this every time and waldo will fail us 
        self.connected = True
        print("Connected to the server.")
        
    




