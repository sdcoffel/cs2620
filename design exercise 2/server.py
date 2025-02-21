import socket
import threading
from accounts import *
from messages import *

#GLOBALS - DO NOT MOVE
FILE_PATH = "all_accounts_ever.txt"
MESSAGES_FILE_PATH = "all_messages_ever.txt"
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
messages = {}
pending_messages = {}


def send_message(recipient, sender, message):
    """This function will send a message to a specific client. All clients that are currently using the server are stored in the 'active_clients' dict, which
    maps active clients to their respective sockets on the server. This is how the server knows to mediate messages to intended clients.

    All messages that are sent through are stored on the internal database (currently, this is a .txt file containing all messages ever sent).
    If a message is being sent to a user that is not online, it gets saved to the 'pending_messages.txt' file, which holds the messages until the relevant client logs back on.


    Args:
        message: The incoming message from the client.
        sender: The socket that belongs to the sender.
        recipient: The socket that belongs to the recipient. This is where message is being rerouted to

    If we (the server) cannot get a message through, throw an error but do not terminate the connection with the client. Instead we move on to another messaging attempt.
    """

    # save the message internally to our records for future referencing
    create_message(sender, recipient, message, messages)
    save_messages(MESSAGES_FILE_PATH, messages)
    print("Message from {sender} to {recipient} saved to chatlog.")

    if recipient in active_clients and "socket" in active_clients[recipient]:
        client_socket = active_clients[recipient]["socket"]

        try:
            # existing implementation - we send this over as a string over the wire encoded as UTF-8. so the dict format of our messages is turned into a string, and serialized and sent over, as opposed to using JSON
            full_message = f"{sender}: {message}".encode("utf-8")
            client_socket.send(full_message)

            print(f"Message from {sender} to {recipient} delivered.")

        except Exception as e:
            print(f"Failed to send message from {sender} to {recipient}: {e}")

    else:
        if recipient not in messages:
            pending_messages[recipient] = []

        pending_messages[recipient].append((sender, message))
        save_pending_messages(PENDING_MESSAGES_FILE_PATH, recipient, sender, pending_messages)
        print(f"Message from {sender} to {recipient} saved as a pending message by the server.")


def login_protocol(connection, accounts):
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
        if not JSON_MODE:
            credentials = connection.recv(1024).decode().strip().split(",")
            username, password, existing = (
                credentials[0],
                credentials[1],
                credentials[2],
            )

        try:
            # if the user is trying to create a new account
            if existing == "no":
                if username in accounts:
                    connection.send("Username already exists. Please try again.\n".encode("utf-8"))

                else:
                    create_account(username, password, FILE_PATH)
                    connection.send("Account created! You are now logged in.\n".encode("utf-8"))

                    return username

            # if the user is logging into a preexisting account
            elif existing == "yes":
                if username in accounts and password == accounts[username]["password"]:
                    connection.send("Success! You are now logged in.\n".encode("utf-8"))

                    return username

                else:
                    connection.send("This username/password is not registered with us! Please try again.\n".encode("utf-8"))
                    continue

        except ValueError as e:
            connection.send(f"Account creation failed: {e}. Please try again.\n".encode("utf-8"))
            continue


def handle_pending_messages(connection, username):
    """This function displays the most recent 10 pending messages for the user on login. If JSON_MODE is off,
    the messages are processed on the server and then sent over the wire to the client as a string, which the client will then decode.
    Otherwise, it is sent in JSON format.
    """

    pending_messages = load_pending_messages(PENDING_MESSAGES_FILE_PATH)

    if username in pending_messages:
        # grab the first 10 messages to send to the client
        message_list = pending_messages[username]
        num_pending_messages = len(message_list)
        message_limit = message_list[-10:]

        # prepare the message for sending and update our internal database
        pending_message_info = f"You have pending messages: \n"
        for sender, message in message_limit:
            full_message = f"{sender}: {message}\n"
            pending_message_info += full_message
            create_message(sender, username, message, messages)

        # save the messages to our internal database after removing them from the pending_messages logs
        save_messages(MESSAGES_FILE_PATH, messages)

        # send messages over to the client in the chosen format
        connection.send(pending_message_info.encode("utf-8"))

        if len(message_list) > 10:
            pending_messages[username] = message_list[:-10]

        delete_pending_messages(PENDING_MESSAGES_FILE_PATH, username, 10) #for some reason this stuff is not getting deleted 
        print(f"Pending messages for {username} sent to {username}.")

    else:
        connection.send("You have 0 pending messages.\n".encode("utf-8"))


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


def handle_more_messages(connection, username):
    """If there are more than 10 pending messages, the user can request to see the rest of them in chunks of 10 on login by clicking the 'more' button on the GUI.
    That button will call this function. This function will grab the next 10 messages from the pending queue, send them over to the client, and store those messages in our
    internal database by moving them from the pending_messages file to all_messages_ever.

    Args:
        connection (socket.socket()): socket associated with the client
        username: the client's chosen username
    """

    if username in pending_messages and pending_messages[username]:
        message_list = pending_messages[username]
        if message_list:
            message_limit = message_list[-10:]
            more_message_info = ""
            for sender, message in message_limit:
                full_message = f"{sender}: {message}\n"
                more_message_info += full_message


            connection.send(more_message_info.encode("utf-8"))
            create_message(sender, username, message, messages)
            save_messages(MESSAGES_FILE_PATH, messages)
            pending_messages[username] = message_list[:-10]
            delete_pending_messages(PENDING_MESSAGES_FILE_PATH, username, 10)

            if not pending_messages[username]:
                connection.send("No more messages.\n".encode("utf-8"))

        else:
            connection.send("No more messages.\n".encode("utf-8"))

    else:
        connection.send("No more messages.\n".encode("utf-8"))


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



def client_handler(connection, address):
    """Establishes a connection with the client, prompts for login info, and prompts for the recipient of any messages.
    There are a few supported options here. Clients can:
        -make a new account/delete an account
        -login to preexisting accounts (with validation criteria)
        -delete messages that have been sent in the chat
        -request to see pending messages from when they were offline, or continue without viewing those messages
        -list all the accounts that are registered on the server
        -change which account they are messaging in-chat

    Args:
        connection (socket.socket()): socket associated with the client
        address: IP address and port number of the client
    """

    username = None  # initially set to None, filled in upon login when user supplies their credentials
    try:
        print(f"Connected with {address}")

        """Login protocols."""

        accounts = load_accounts(FILE_PATH)
        username = login_protocol(connection, accounts)
        active_clients[username] = {"socket": connection}
        print(f"{username} has connected.\n")

        handle_pending_messages(connection, username)

        """Main message loop. Keywords come through for special commands - since everything is passed through as strings in our custom wire protocol, the server will listen for 
            these specific keywords from the client/GUI and do specific operations if it hears them. The message that gets sent over the wire is stored in 'raw_message'."""

        while True:

            raw_message = connection.recv(1024).decode().strip()

            if not raw_message:
                break

            # handle account deletions
            if raw_message.lower() == "delete_account":
                handle_account_deletion(connection, username)

            # list accounts by wildcard
            elif raw_message.lower() == "list_accounts":
                print(f"List requested by user {username}")
                all_clients = list_accounts(FILE_PATH)
                connection.send(all_clients.encode("utf-8"))
                continue

            # delete a message, or set of messages
            elif raw_message.lower().startswith("delete"):
                _, message_content = raw_message.split(" ", 1)
                delete_message_handler(connection, message_content)
                continue

            # see if there are more pending messages that need to be displayed
            elif raw_message.lower() == "more":
                handle_more_messages(connection, username)

            # proceed to the messaging screen on the GUI
            elif raw_message.lower() == "done":
                continue

            # we don't need this, but its good to know server-side who is logging on or off
            elif raw_message.lower() == "logout":
                print(f"{username} has logged out")

            # all other messages that don't have special command associated with them (i.e. messages that the user intends to send as messages) go through here
            if ":" in raw_message:
                recipient, msg = raw_message.split(":", 1)
                send_message(recipient, username, msg)

            else:
                # handle setting the recipient and tracking in the server
                recipient = raw_message

                if recipient in accounts:
                    active_clients[username]["recipient"] = recipient
                    print(f"{username} is messaging {recipient}.")

                else:
                    pass

    except Exception as e:
        print(f"Errors: {e}")

    finally:
        connection.close()
        print(f"{username} has disconnected")


def start_server():
    """Responsible for booting up the server.
    This will run until the server encounters an exception or is manually shut off. Here, the server listens for a client who wishes to connect, then starts a thread for that client.
    This ensures that we can have multiple clients running together, all on separate threads.
    """


    global pending_messages
    load_pending_messages(PENDING_MESSAGES_FILE_PATH)
    print("Pending messages loaded...")

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        port = 12345
        server_socket.bind(("0.0.0.0", port))  # listens on all interfaces for the client
        server_socket.listen()
        print(f"Server is listening on port {port}")

        while True:
            try:
                client_socket, addr = server_socket.accept()
                thread = threading.Thread(target=client_handler, args=(client_socket, addr))
                thread.start()

            except Exception as e:
                print(f"Fatal error {e} with server")

    finally:
        try:
            save_pending_messages(PENDING_MESSAGES_FILE_PATH, pending_messages)
            print("Pending messages saved...")
            server_socket.close()

        except Exception as e:
            print(f"Failed to close server socket properly! : {e}")


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
