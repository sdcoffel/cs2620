import grpc 
from concurrent import futures 
import time 
import queue

import chatapp_pb2
import chatapp_pb2_grpc

from accounts import *
from messages import *

#GLOBALS - DO NOT MOVE
FILE_PATH = "all_accounts_ever.txt"
MESSAGES_FILE_PATH = "all_messages_ever.txt"
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
messages = {}
pending_messages = {}

class ChatServer(chatapp_pb2_grpc.ChatServiceServicer):


    def Login(self, request, context):
        """This function handles the login protocol for the client. Duplicate/bad usernames that don't match with our internal databases send a warning message to the client.

        If the client is creating a new account, we check for usernames that already exist in our database. If the client provides a dupe, we tell them. If the client
        provides a good username, we save the newly created account to our records and let them in.

        If the client is logging in, we check that the username they provide is a username in our database, and we validate the password with what we have stored.
        Our passwords are all hashed, so the hashed password comes in from the client side, and that is what we cross-check with our records.

        On bad login attempts, users can attempt to log in as many times as necessary. Succesful logins take you to the pending messages board.

        Args:
            connection (socket.socket()): socket associated with the client
            accounts: the dict of all accounts that are registered on the server, for cross-validation

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
                        return chatapp_pb2.LoginResponse(success=True, message="Account created! You are now logged in.")

                #if the user is logging into a preexisting account
                else:
                    if username in accounts and password == accounts[username]["password"]:
                        return chatapp_pb2.LoginResponse(success=True, message="Success! You are now logged in.")
                    
                    else:
                        return chatapp_pb2.LoginResponse(success=False, message="This username/password is not registered with us!")


            except ValueError as e:
                print(f"Client log: Account creation failed. Try again")
                continue


    def GetPendingMessages(self, request, context):
        """This function displays the most recent 10 pending messages for the user on login. 
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
                create_message(sender, request.username, msg, messages)
                #add to pending messages database
                messages_list.append(chatapp_pb2.PendingMessage(sender=sender, message=msg))
            
            #save updates
            save_messages(MESSAGES_FILE_PATH, messages)
            
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
        """If there are more than 10 pending messages, the user can request to see the rest of them in chunks of 10 on login by clicking the 'more' button on the GUI.
        That button will call this function. This function will grab the next 10 messages from the pending queue, send them over to the client, and store those messages in our
        internal database by moving them from the pending_messages file to all_messages_ever.

        Args:
            connection (socket.socket()): socket associated with the client
            username: the client's chosen username
        """

        if request.username in pending_messages and pending_messages[request.username]:
            message_list = pending_messages[request.username]
            if message_list:
                #get most recent 10 messages
                message_limit = message_list[-10:]
                messages_list = []
                for sender, msg in message_limit:
                    messages_list.append(chatapp_pb2.PendingMessage(sender=sender, message=msg))

                #log messages
                for sender, msg in message_limit:
                    create_message(sender, request.username, msg, messages)
                save_messages(MESSAGES_FILE_PATH, messages)

                #remove messages from pending list
                pending_messages[request.username] = message_list[:-10] #do i need this???
                delete_pending_messages(PENDING_MESSAGES_FILE_PATH, request.username, 10)

                #return the retrieved messages.
                return chatapp_pb2.MoreMessagesResponse(messages=messages_list, message="More messages retrieved.")
            
            else:
                return chatapp_pb2.MoreMessagesResponse(messages=[], message="No more messages.\n")
        else:
            return chatapp_pb2.MoreMessagesResponse(messages=[], message="No more messages.\n")


    def SendMessage(self, request, context):
        """This function will send a message to a specific client. All clients that are currently using the server are stored in the 'active_clients' dict, which
        maps [update this ]

        All messages that are sent through are stored on the internal database (currently, this is a .txt file containing all messages ever sent).
        If a message is being sent to a user that is not online, it gets saved to the 'pending_messages.txt' file, which holds the messages until the relevant client logs back on.

        Args:
            to be updated 

        If we (the server) cannot get a message through, throw an error but do not terminate the connection with the client. Instead we move on to another messaging attempt.
        """

        # save the message internally to our records for future referencing
        create_message(request.sender, request.recipient, request.message, messages)
        save_messages(MESSAGES_FILE_PATH, messages)
        print(f"Message from {request.sender} to {request.recipient} saved to chatlog.")


        #if the recipient is online, i.e., their queue is active, deliver in real time.
        if request.recipient in active_clients:
            client_queue = active_clients[request.recipient]
            client_queue.put((request.sender, request.message))

            print(f"Message from {request.sender} to {request.recipient} delivered via queue.")
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
        A server-streaming RPC that continuously yields new messages for the given user.
        It first pushes any pending messages into the client's queue. Otherwise, it's forwarded immediately.
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
            delete_pending_messages(PENDING_MESSAGES_FILE_PATH, request.username, 10)  # Adjust as needed.

        #stream messages to the client in real time
        while True:
            try:
                sender, msg = client_queue.get(timeout=0) #immediate - although i want to clean this up a lot
                yield chatapp_pb2.ChatMessageResponse(sender=sender, message=msg)
            except queue.Empty:
                #keep waiting
                continue


    def delete_message_handler(connection, message_content):
        """This function deletes messages from the server's internal database, and sends a message to the client confirming message deletion. It is mostly for our recordkeeping,
        as the messages are erased from the GUI using GUI-specific magic.

        Args:
            connection (socket.socket()): socket associated with the client
            message_content: the message that the client wants to delete
        """

        if delete_message(message_content, MESSAGES_FILE_PATH): 
            connection.send(f"Message with content '{message_content}' deleted successfully.".encode("utf-8"))
            print("Message deleted from chatlog.")

        else:
            connection.send(f"Message with content '{message_content}' not found.".encode("utf-8"))


    def handle_account_deletion(connection, username):
        """This function allows users to delete their accounts. The user is prompted for a confirmation, and if the user says yes, the function calls delete_account()
        which deletes the user's account from the database and sends a message to the client. On the GUI, the window is also promptly closed.
        If the user chooses not to delete their account, nothing happens, and we proceed as normal.

        Args:
            (socket.socket()): socket associated with the client
            username: the client's chosen username
        """

        if username in pending_messages and pending_messages[username]:

            connection.send("You have unread messages. Are you sure you want to delete your account?".encode("utf-8"))
            confirmation = connection.recv(1024).decode().strip().lower()

            # user has decided to delete their account
            if confirmation == "yes":
                delete_account(username, FILE_PATH)
                delete_pending_messages(PENDING_MESSAGES_FILE_PATH, username, len(pending_messages[username]))  # deletes all pending messages as well as the account itself
                print(f"Account deletion successful for user {username}")

            else:
                # the user has decided not to delete their account in the GUI
                print(f"{username} aborted deletion") 
                connection.send("Account deletion aborted.".encode("utf-8"))

        # if the account has no associated pending messages, delete. there will still be a prompt on the GUI, but no need to do operations serverside here
        delete_account(username, FILE_PATH)
        print(f"Account deletion requested by user {username}")
        connection.send("Account deleted successfully.".encode("utf-8"))


    # def client_handler(connection, address):
    #     """Establishes a connection with the client, prompts for login info, and prompts for the recipient of any messages.
    #     There are a few supported options here. Clients can:
    #         -make a new account/delete an account
    #         -login to preexisting accounts (with validation criteria)
    #         -delete messages that have been sent in the chat
    #         -request to see pending messages from when they were offline, or continue without viewing those messages
    #         -list all the accounts that are registered on the server
    #         -change which account they are messaging in-chat

    #     Args:
    #         connection (socket.socket()): socket associated with the client
    #         address: IP address and port number of the client
    #     """

    #     username = None  # initially set to None, filled in upon login when user supplies their credentials
    #     try:
    #         print(f"Connected with {address}")

            #i feel like i still need these....
    #         accounts = load_accounts(FILE_PATH)
    #         username = login_protocol(connection, accounts)
    #         active_clients[username] = {"socket": connection} #this could be a problem later....
    #         print(f"{username} has connected.\n")


            # while True:
            #     raw_message = connection.recv(1024).decode().strip()

            #     if not raw_message:
            #         break

            #     # handle account deletions
            #     if raw_message.lower() == "delete_account":
            #         handle_account_deletion(connection, username)

            #     # list accounts by wildcard -- this needs its own function 
            #     elif raw_message.lower() == "list_accounts":
            #         print(f"List requested by user {username}")
            #         all_clients = list_accounts(FILE_PATH)
            #         connection.send(all_clients.encode("utf-8"))
            #         continue

            #     # delete a message, or set of messages
            #     elif raw_message.lower().startswith("delete"):
            #         _, message_content = raw_message.split(" ", 1)
            #         delete_message_handler(connection, message_content)
            #         continue


            #     # we don't need this, but its good to know server-side who is logging on or off
            #     elif raw_message.lower() == "logout":
            #         print(f"{username} has logged out")

            #     # all other messages that don't have special command associated with them (i.e. messages that the user intends to send as messages) go through here
            #     if ":" in raw_message:
            #         recipient, msg = raw_message.split(":", 1)
            #         send_message(recipient, username, msg)

            #     else:
            #         # handle setting the recipient and tracking in the server -- i feel like i still need this 
            #         recipient = raw_message

            #         if recipient in accounts:
            #             active_clients[username]["recipient"] = recipient
            #             print(f"{username} is messaging {recipient}.")

            #         else:
            #             pass

        # except Exception as e:
        #     print(f"Errors: {e}")

        # finally:
        #     connection.close()
        #     print(f"{username} has disconnected")



def start_server():
    """Responsible for booting up the server.
    This will run until the server encounters an exception or is manually shut off. Here, the server listens for a client who wishes to connect, then starts a thread for that client.
    This ensures that we can have multiple clients running together, all on separate threads.
    """


    global pending_messages
    load_pending_messages(PENDING_MESSAGES_FILE_PATH)
    print("Pending messages loaded...")

    try:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        chatapp_pb2_grpc.add_ChatServiceServicer_to_server(ChatServer(), server)
        server.add_insecure_port('[::]:50051')
        server.start()
        print(f"Server is listening on port 50051...")

        try: 
            while True: 
                time.sleep(86400) #this is the only way to keep the while loop running for a long time- has to be a better way than this
        except KeyboardInterrupt: 
            server.stop(0)


    except Exception as e: 
        print(f"Fatal error {e} with server")


    finally:
        try:
            #save_pending_messages(PENDING_MESSAGES_FILE_PATH, pending_messages)
            print("Pending messages saved...")
            #server_socket.close()

        except Exception as e:
            print(f"Failed to exit server properly! : {e}")


if __name__ == "__main__":
    # call all globally scoped vars
    FILE_PATH 
    MESSAGES_FILE_PATH 
    PENDING_MESSAGES_FILE_PATH
    active_clients 
    messages 
    pending_messages 

    #fire up the server
    start_server()
