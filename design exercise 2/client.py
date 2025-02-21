#import socket
import grpc
import hashlib
import re

import chatapp_pb2
import chatapp_pb2_grpc

class Client:

    def __init__(self, host = 'localhost', port= 50051):
        """Initialize the client."""

        self.channel = None
        self.stub = None
        self.username = None


    @staticmethod
    def hash_password(password):
        """Hash a password for storing. This uses hashlib to hash the password and then send it over the network."""
        return hashlib.sha256(password.encode()).hexdigest()


    def receive_messages(self):
        """This function is in charge of receiving messages that have been forwarded from the server.

        Returns:
            Will return with an exception if the connection between the server and the client goes down. Else will continue until either the client or server
            terminates the connection. Depending on whether JSON_MODE is turned on or off, data will be sent either as encoded strings or under the JSON protocol.
        """

        message = self.client_socket.recv(4096).decode("utf-8")
        if message:
            print("\rReceived: " + message + "\nYou: ", end="")

        else:
            print("\nServer closed the connection.")
        
        return message
    

    def send_messages(self, recipient, message):
        """Sends messages along the socket to the server. If an empty message is typed, the user has the power to
        terminate the connection when prompted. Different error handling mechanisms are at the bottom of the function.
        The user can exit the chat by typing 'quit', change the intended recipient by typing 'change', or delete a message that was sent during that session by typing 'delete'.

        Args:
            recipient (str): The recipient username
            message (str): The message content
        """

        full_message = f"{recipient}:{message}"
        self.client_socket.send(full_message.encode("utf-8"))
            

    def delete_message(self, message):
        """Sends a request to delete a message from the server.

        Args:
            message (str): The content (or partial content) of the message to be deleted.
        """

        #good for client-side awareness: printing the server message to confirm things are working as they should 
        self.client_socket.send(("delete" + message).encode("utf-8"))
        server_message = self.client_socket.recv(1024).decode("utf-8")
        print(server_message)


    def handle_login(self, username, password, existing):
        """Handles the login process for the client. This prompts the user for their login data, and sends it to the server for credential validation. The password is 
        hashed client-side and then sent over the network for the server to store and reference later. 

        If the user is creating a new account, 'existing' is marked as no. If they are logging into a preexisting account, 'existing' is marked as yes. 

        Args:
            username (str): The username to log in with
            password (str): The password to log in with
            existing (str): "yes" or "no", indicating if the account already exists
        """

        #password gets hashed
        hashed_password = self.hash_password(password)

        #convert the "existing" flag: if user inputs "no", then is_new is True which triggers the create new account cond. in server
        is_new = True if existing.lower() == "no" else False
        
        #create the LoginRequest message 
        login_request = chatapp_pb2.LoginRequest(username=username, password=hashed_password, is_new=is_new)
        
        #call the Login RPC
        response = self.stub.Login(login_request)
        print("Server response:", response.message)
        
        #store username and move on 
        if response.success:
            self.username = username
        return response.success, response.message
        

    def get_pending_messages(self):
        """Grab any pending messages after login. The server automatically sends these right after login.
        If the user has any pending messages, these are handled at login and displayed for the client to see in bunches of 10 messages. 
        The client can request to see another 10 messages at a time if they wish to see more by calling relevant functions in the server.

        Returns:
            The pending messages as a string for the GUI to display
        """

        pending_message_info = self.client_socket.recv(4096).decode("utf-8")
        print(pending_message_info)
        return pending_message_info
        

    def grab_more_messages(self):
        """Requests more messages from the server if the user wants to see the next batch of 10 pending messages. 

        Returns:
            The server's response, either JSON or plain text. The response is the next 10 messages if they exist, otherwise it will say 'no more messages'.
        """

        self.client_socket.send("more".encode("utf-8"))
        more_messages = self.client_socket.recv(4096).decode("utf-8")
        return more_messages


    def delete_account(self):
        """Sends a request to the server to delete the user's account. The operation is done on the serverside, 
        and the confirmation is sent to the client for a sanity check.

        Returns:
            The server message response (plain text or JSON).
        """

        #print the deletion confirmation to console for a sanity check
        self.client_socket.send("delete_account".encode("utf-8"))
        server_message = self.client_socket.recv(1024).decode("utf-8")
        print(server_message)
        return server_message


    def confirm_deletion(self, server_message, confirmation):
        """Handles the confirmation step in the GUI when the server notifies the user they have unread messages
        and asks if they're sure about deleting the account. The server waits for the confirmation before the account is removed from the database.

        Args:
            server_message (str): The server's initial message (which may mention unread messages).
            confirmation (str): The user's response ("yes" or "no").

        Returns:
            The server response after confirmation, and a boolean indicating a successful deletion or not. 
        """

        if "You have unread messages" in server_message:
            #confirm the account deletion request 
            self.client_socket.send(confirmation.encode("utf-8"))
            server_message = self.client_socket.recv(1024).decode("utf-8")
            return server_message
        
        else:
            return False
        

    def list_accounts(self):
        """Requests from the server the list of all accounts.

        Returns:
            The list of accounts (as plain text or JSON-parsed list).
        """

        self.client_socket.send("list_accounts".encode("utf-8"))
        server_message = self.client_socket.recv(1024).decode("utf-8")
        accounts = server_message.split("\n")
        return accounts


    def wildcard(self, pattern, accounts):
        """Filter the list of accounts by a pattern.

        Args:
            pattern (str): The pattern to match ("all" or a regex).
            accounts (list): The list of accounts.

        Returns:
            A filtered list of accounts or a string if none match.
        """
        
        if pattern.lower() == "all":
            filtered_accounts = accounts
        else:
            filtered_accounts = [account for account in accounts if re.search(pattern, account)]

        if not filtered_accounts:
            return "No accounts match the given pattern."

        return filtered_accounts


    def set_recipient(self, recipient):
        """Sets the intended recipient for future messages The server will process this and assign the recipient to a socket that the server will manage.

        Args:
            recipient (str): The username of the recipient.
        """

        self.client_socket.send(recipient.encode("utf-8"))


    def start_client(self, host, port):
        """Responsible for booting up the client and establishing the first connection to the server. Connects to the server on a localhost port.

        Args:
            host (str): The server IP or hostname. We can text each other over not as strongly encrypted wifi like 'Harvard University'. Eduroam might be too encrypted lol.
            port (int): The server's designated listening port. This is assigned in the server as '12345'
        """

        try:
            self.channel = grpc.insecure_channel(f'{host}:{port}')
            self.stub = chatapp_pb2_grpc.ChatServiceStub(self.channel)
            # self.client_socket.connect((host, port))
            # self.connected = True
            print("Connected to the server.")

        except Exception as e: 
            print("Failed to connect to the gRPC server. Client needs to retry.")
            