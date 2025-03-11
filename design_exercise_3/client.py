import grpc
import hashlib
import chatapp_pb2
import chatapp_pb2_grpc

class Client:

    def __init__(self, host, port= 50051):
        """Initialize the client."""

        self.channel = None
        self.stub = None
        self.username = None


    @staticmethod
    def hash_password(password):
        """Hash a password for storing. This uses hashlib to hash the password and then send it over the network."""
        return hashlib.sha256(password.encode()).hexdigest()


    def handle_login(self, username, password, existing):
        """Handles the login process for the client. This prompts the user for their login data, and sends it to the server for credential validation. The password is 
        hashed client-side and then sent over the network for the server to store and reference later. 

        If the user is creating a new account, 'existing' is marked as no. If they are logging into a preexisting account, 'existing' is marked as yes. 

        Args:
            username (str): The username to log in with
            password (str): The password to log in with
            existing (str): "yes" or "no", indicating if the account already exists

        Returns: 
            response.success (bool), response.message (str): flag for a successful login, and the corresponding message.
        """

        #password gets hashed
        hashed_password = self.hash_password(password)

        #convert the "existing" flag: if user inputs "no", then is_new is True which triggers the create new account cond. in server
        is_new = True if existing.lower() == "no" else False
        
        #create the LoginRequest message and call the RPC
        login_request = chatapp_pb2.LoginRequest(username=username, password=hashed_password, is_new=is_new)
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

        request = chatapp_pb2.PendingMessagesRequest(username=self.username)
        response = self.stub.GetPendingMessages(request)
        
        if response.messages:
            display_text = "\n".join([f"{msg.sender}: {msg.message}" for msg in response.messages])

        else:
            display_text = response.message + "\n" #"You have 0 pending messages."
        
        print(f"For client records: {display_text}")
        return display_text


    def grab_more_messages(self):
        """Requests more messages from the server if the user wants to see the next batch of 10 pending messages. 

        Returns:
            The server's response as the next 10 messages if they exist, otherwise it will say 'no more messages'.
        """

        request = chatapp_pb2.MoreMessagesRequest(username=self.username)
        response = self.stub.MoreMessages(request)
        return response.message
    

    def set_recipient(self, recipient):
        """Stores the default recipient locally so that future send_messages calls can use it.
        This is also convenient because you can change the intended recipient in the GUI at will here.
        """
        
        self.recipient = recipient
        print(f"Default recipient set to {recipient}")


    def ReceiveMessages(self):
        """
        Opens a streaming RPC to receive messages in real time.
        This blocks and yields messages to the GUI as they arrive.
        """

        request = chatapp_pb2.ReceiveMessagesRequest(username=self.username)
        try:
            for chat_msg in self.stub.ReceiveMessages(request):
                message_str = f"Received from {chat_msg.sender}: {chat_msg.message}"
                print(message_str) #so i can debug from terminal lol
                yield message_str
        except grpc.RpcError as e:
            print("Message stream closed:", e)
    

    def send_messages(self, recipient, message):
        """
        Sends a message by calling the SendMessage RPC.

        Returns:
            the message data that is displayed in the GUI.
        """

        #if the recipient doesn't exist yet 
        if not hasattr(self, "recipient") or not self.recipient:
            print("No recipient set.")
            return False
    
        request = chatapp_pb2.SendMessageRequest(sender=self.username, recipient=recipient, message=message)
        response = self.stub.SendMessage(request)
        print("Server response:", response.message)
        return response.delivered
            

    def delete_account(self):
        """Sends a request to the server to delete the user's account. The operation is done on the serverside, 
        and the confirmation is sent to the client for a sanity check.

        Returns:
            The server message response.
        """

        #print the deletion confirmation to console for a sanity check
        request = chatapp_pb2.DeleteAccountRequest(username=self.username, confirm=True)
        response = self.stub.DeleteAccount(request)
        print("Server response:", response.message)
        return response.message


    def list_accounts(self, filter = "all"):
        """Requests the list of all accounts from server.

        Returns:
            The list of accounts.
        """

        request = chatapp_pb2.ListAccountsRequest(filter=filter)
        response = self.stub.ListAccounts(request)
        print("Server message:", response.message)
        return response.accounts


    def start_client(self, host, port):
        """Responsible for booting up the client and establishing the first connection to the server. Connects to the server on a localhost port.

        Args:
            host (str): The server IP or hostname. We can text each other over not as strongly encrypted wifi like 'Harvard University'. Eduroam might be too encrypted lol.
            port (int): The server's designated listening port. This is assigned in the server as '50051'
        """

        try:
            self.channel = grpc.insecure_channel(f'{host}:{port}')
            self.stub = chatapp_pb2_grpc.ChatServiceStub(self.channel)
            print("Connected to the server.")

        except Exception as e: 
            print("Failed to connect to the gRPC server. Client needs to retry.")


