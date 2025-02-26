import grpc 
import time 
import queue
import re
import chatapp_pb2
import chatapp_pb2_grpc
from concurrent import futures 
from accounts import *
from messages import *

#GLOBALS - DO NOT MOVE
FILE_PATH = "all_accounts_ever.txt"
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
pending_messages = {}

class ChatServer(chatapp_pb2_grpc.ChatServiceServicer):

    def Login(self, request, context):
        """This function handles the login protocol for the client. Duplicate/bad usernames that don't match with our internal databases send a warning message to the client.

        This method receives a LoginRequest containing a username, a hashed password, and a boolean flag indicating whether the request is for account creation (is_new=True)
        or for logging into an existing account (is_new=False). 

        For account creation, the server checks whether the username already exists in its database.
        If it does, a failure response is returned; otherwise, the account is created and a success response is sent. 
        For login requests, the method validates the provided username and hashed password against the stored credentials. 
        If the credentials match, a success response is returned; otherwise, an error message is sent back.

        On invalid input or verification failure, the server returns a LoginResponse with success set to False along with an error message.
        On bad login attempts, users can attempt to log in as many times as necessary. Succesful logins take you to the pending messages board.

        Args:
            request (LoginRequest): A gRPC request message containing:
                - username (str): user's username.
                - password (str): user's hashed password.
                - is_new (bool): True for new account creation; False for logging in.
                - context (grpc.ServicerContext): RPC-specific information like deadlines and metadata.

        Returns:
            LoginResponse: A gRPC response message with:
                - success (bool): True if login or account creation is successful; False otherwise.
                - message (str): A descriptive message indicating the outcome of the operation.

        """
        # grab credentials that came over from the client
        while True:
            #grab credentials 
            accounts = load_accounts(FILE_PATH)
            username = request.username
            password = request.password  
            is_new = request.is_new

            try:
                #if the user is trying to create a new account
                if is_new:
                    if username in accounts:
                        return chatapp_pb2.LoginResponse(success=False, message="Username already exists. Please try again.")
                    
                    else:
                        create_account(username, password, FILE_PATH)
                        print(f"{username} has connected.")
                        return chatapp_pb2.LoginResponse(success=True, message="Account created! You are now logged in.")

                #if the user is logging into a preexisting account
                else:
                    if username in accounts and password == accounts[username]["password"]:
                        print(f"{username} has connected.")
                        return chatapp_pb2.LoginResponse(success=True, message="Success! You are now logged in.")
                    
                    else:
                        return chatapp_pb2.LoginResponse(success=False, message="This username/password is not registered with us!")
                    
            except ValueError as e:
                print(f"Client log: Account creation failed. Try again")
                continue


    def GetPendingMessages(self, request, context):
        """This function displays the most recent 10 pending messages for the user on login by loading the pending messages 
        from persistent storage for the user identified in the request.
        It selects the last (most recent) 10 messages and formats them as a list of PendingMessage objects. 
        Finally, the method updates the pending messages store and deletes them from persistent storage.

        Args:
            request (PendingMessagesRequest): A request message containing:
                - username (str): The username for which pending messages are to be retrieved.
                - context (grpc.ServicerContext): RPC-specific information (deadlines, metadata, etc.).

        Returns:
            PendingMessagesResponse: A response message containing:
                - messages (repeated PendingMessage): The list of up to 10 pending messages.
                - message (str): A summary string of the pending messages or indication that no pending messages exist.

        """

        pending = load_pending_messages(PENDING_MESSAGES_FILE_PATH)
        messages_list = []
        if request.username in pending:

            #grab most recent 10 messages
            message_list = pending[request.username]
            message_limit = message_list[-10:]
            pending_message_info = "You have pending messages: \n"
            
            for sender, msg in message_limit:
                pending_message_info += f"{sender}: {msg}\n"

                #save to records
                messages_list.append(chatapp_pb2.PendingMessage(sender=sender, message=msg))
                      
            #remove the sent messages from the pending database
            if len(message_list) > 10:
                pending[request.username] = message_list[:-10]
            else:
                pending[request.username] = []
            
            #delete pending messages from the database -- am i double deleting here??? 
            delete_pending_messages(PENDING_MESSAGES_FILE_PATH, request.username, 10)
            print(f"Pending messages for {request.username} sent to {request.username}.")
            return chatapp_pb2.PendingMessagesResponse(messages=messages_list, message=pending_message_info)
        
        else:
            #if there are no pending messages:
            return chatapp_pb2.PendingMessagesResponse(messages=[], message = "You have 0 pending messages.\n")


    def MoreMessages(self, request, context):
        """Constructs a list of 10 more PendingMessage objects representing these messages, updates the internal pending messages
        store by removing the messages that have been retrieved, and deletes these messages from persistent storage.

        Args:
            request (MoreMessagesRequest): A request message containing:
                - username (str): The username for which additional pending messages are requested.
                - context (grpc.ServicerContext): RPC-specific info.

        Returns:
            MoreMessagesResponse: A response message containing:
                - messages (repeated PendingMessage): A list of up to 10 pending messages.
                - message (str): A string indicating the result.
        """

        if request.username in pending_messages and pending_messages[request.username]:
            message_list = pending_messages[request.username]
            if message_list:
                #get most recent 10 messages
                message_limit = message_list[-10:]
                messages_list = []
                for sender, msg in message_limit:
                    messages_list.append(chatapp_pb2.PendingMessage(sender=sender, message=msg))

                #remove messages from pending list
                pending_messages[request.username] = message_list[:-10] #do i need this???
                delete_pending_messages(PENDING_MESSAGES_FILE_PATH, request.username, 10)

                #return the retrieved messages.
                return chatapp_pb2.MoreMessagesResponse(messages=messages_list, message="More messages retrieved.\n")
            
            else:
                return chatapp_pb2.MoreMessagesResponse(messages=[], message="No more messages.\n")
        else:
            return chatapp_pb2.MoreMessagesResponse(messages=[], message="No more messages.\n")


    def SendMessage(self, request, context):
        """This function will send a message to a specific client. 
        If the intended recipient is online, the message is delivered in real time by placing it into that client's queue.
        If the recipient is offline, the message is appended to the 'pending_messages' store and saved to persistent storage, so it can be delivered when the recipient logs in.

        Args:
            request (SendMessageRequest): A request message containing:
                - sender (str): The username of the client sending the message.
                - recipient (str): The username of the intended recipient.
                - message (str): The content of the message.
                - context (grpc.ServicerContext): context for the RPC call

        Returns:
            SendMessageResponse: A response message indicating whether the message was delivered in real time (delivered=True) or saved as pending (delivered=False).
        """

        #if the recipient is online, i.e., their queue is active, deliver in real time.
        if request.recipient in active_clients:
            client_queue = active_clients[request.recipient]
            client_queue.put((request.sender, request.message))

            print(f"{request.sender} is messaging {request.recipient}.")
            print(f"Message from {request.sender} to {request.recipient} delivered.")

            return chatapp_pb2.SendMessageResponse(delivered=True, message="Message delivered.")
        
        else:
            #store to pending messages if intended recipient is not online
            if request.recipient not in pending_messages:
                pending_messages[request.recipient] = []

            pending_messages[request.recipient].append((request.sender, request.message))
            save_pending_messages(PENDING_MESSAGES_FILE_PATH, request.recipient, request.sender, pending_messages)

            print(f"Message from {request.sender} to {request.recipient} saved as pending.")
            return chatapp_pb2.SendMessageResponse(delivered=False, message="Recipient offline. Message saved as pending.")


    def ReceiveMessages(self, request, context):
        """
        Server-streaming RPC that continuously yields new chat messages for the user.
        Ensures that the user's message queue exists and queues any pending messages from persistent storage. 
        When a message is available, this yields a ChatMessageResponse containing the sender and message content. The loop continues as long as the RPC context is active.
        
        Args:
            request (ReceiveMessagesRequest): The request message containing:
                - username (str): The username of the client that will receive messages.
                - context (grpc.ServicerContext):  RPC-specific info
            
        Yields:
            ChatMessageResponse: A stream of chat messages (each with a sender and message field) for the client.
        """
        #make sure the user's queue is actually there
        if request.username not in active_clients:
            active_clients[request.username] = queue.Queue()
        client_queue = active_clients[request.username]

        #pending messages get added to the queue
        if request.username in pending_messages:
            for sender, msg in pending_messages[request.username]:
                client_queue.put((sender, msg))
            pending_messages[request.username] = []
            delete_pending_messages(PENDING_MESSAGES_FILE_PATH, request.username, 10) 

        #stream messages to the client in real time. if we ever happen to hit an empty queue, just continue 
        while context.is_active():
            try:
                sender, msg = client_queue.get(timeout=0) #immediate - although i want to clean this up a lot
                yield chatapp_pb2.ChatMessageResponse(sender=sender, message=msg)

            except queue.Empty:
                continue


    def DeleteAccount(self, request, context):
        """This function allows users to delete their accounts.     
        The request contains the username and a boolean flag (confirm) indicating whether the user has confirmed the deletion
        If there are pending messages and confirmation has not been provided, returns a response prompting the client to confirm deletion. 
        If confirmation is provided or there are no pending messages, the user's account is deleted from the database, and any pending messages are also removed.

        Args:
            request (DeleteAccountRequest): A request message containing:
                - username (str): The username of the account to delete.
                - confirm (bool): True if the user confirms deletion despite unread messages; otherwise, False.
                - context (grpc.ServicerContext): RPC context info, providing metadata and deadlines for the call.

        Returns:
            DeleteAccountResponse: A response message indicating whether the deletion was successful.
        """

        username = request.username
        confirm = request.confirm
        pending = load_pending_messages(PENDING_MESSAGES_FILE_PATH)

        #if there are pending messages, let the user know before they proceed with deleting the account
        if username in pending and pending[username]:
            #if there are unread messages and the user hasn't committed to deleting yet
            if not confirm:
                return chatapp_pb2.DeleteAccountResponse(success=False, message="You have unread messages. Confirm deletion to proceed.")
            
            else:
                #continue with deleting the account and all the pending messages
                delete_account(username, FILE_PATH)
                delete_pending_messages(PENDING_MESSAGES_FILE_PATH, username, len(pending[username]))
                print(f"Account deletion successful for user {username}")
                return chatapp_pb2.DeleteAccountResponse(success=True, message="Account deletion successful.")
            
        else:
            #go ahead and delete the account
            delete_account(username, FILE_PATH)
            print(f"Account deletion requested by user {username}")
            return chatapp_pb2.DeleteAccountResponse(success=True, message="Account deleted successfully.")


    def ListAccounts(self, request, context):
        """
        Obtains all account names from the server's account storage, splits them into a list, and then applies a regex filter if needed. 
        If the filter is empty or set to "all", all accounts are returned. 
        If a regex error occurs, an error message is returned.

        Args:
            request (ListAccountsRequest): A request message containing:
                - filter (str): A regex pattern to filter account names. If empty or "all", no filtering is applied.
                - context (grpc.ServicerContext): The context for the RPC, etc.

        Returns:
            ListAccountsResponse: A response message containing:
                - accounts (repeated string): The list of account names that match the filter.
                - message (str): A message indicating the success/failure of the listing operation.
        """
       
        all_accounts = list_accounts(FILE_PATH)
        accounts = [acct for acct in all_accounts.split("\n") if acct.strip() != ""]
        
        #if we want to wildcard filter, do that here
        if request.filter and request.filter.lower() != "all":
            try:
                filtered_accounts = [acct for acct in accounts if re.search(request.filter, acct)]
            except re.error as err:
                #if there's no matching regex, return invalid message
                return chatapp_pb2.ListAccountsResponse(
                    accounts=[], message=f"No users match this pattern: {err}")
            
        else:
            filtered_accounts = accounts
        
        return chatapp_pb2.ListAccountsResponse(accounts=filtered_accounts, message="Accounts listed successfully.")       


def start_server():
    """Boots up and runs the gRPC server until termination.
    This function:
      - Loads any pending messages from persistent storage.
      - Creates a gRPC server using a ThreadPoolExecutor with up to 10 worker threads.
      - Registers the ChatServiceServicer (i.e., ChatServer) with the gRPC server.
      - Binds the server to port 50051 and starts it.
      - Calls wait_for_termination() to block execution until a termination signal (e.g., KeyboardInterrupt) is received.

    Upon termination (Cntrl+C for us), the function attempts to save any pending messages back to persistent storage before exiting.

    Returns:
        None
    """

    global pending_messages
    load_pending_messages(PENDING_MESSAGES_FILE_PATH)
    print("Pending messages loaded...")

    try:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        chatapp_pb2_grpc.add_ChatServiceServicer_to_server(ChatServer(), server)
        server.add_insecure_port('0.0.0.0:50051')
        server.start()
        print(f"Server is listening on port 50051...")
        server.wait_for_termination() #this is a blocking call that keeps the server running until keyboard interrupt

    except Exception as e: 
        print(f"Fatal error {e} with server")

    finally:
        try:
            save_pending_messages(PENDING_MESSAGES_FILE_PATH, pending_messages)
            print("Pending messages saved...")

        except Exception as e:
            print(f"Failed to exit server properly! : {e}")


if __name__ == "__main__":
    """Call all globally scoped variables, and start up the server."""

    FILE_PATH 
    PENDING_MESSAGES_FILE_PATH
    active_clients 
    pending_messages 
    start_server()
