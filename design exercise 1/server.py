import socket
import threading
from accounts import (
    load_accounts,
    save_accounts,
    create_account,
    is_valid_account,
    delete_account,
    list_accounts,
)
from messages import *

# TODO: wildcard listing for the list accounts function


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

    # maybe adjust this so potentially problematic messages aren't saved to the database
    create_message(sender, recipient, message, messages)
    save_messages(MESSAGES_FILE_PATH, messages)
    print("Message from {sender} to {recipient} saved to chatlog.")

    # assign the desired recipient to a socket and save it in the active_clients dict
    if recipient in active_clients and "socket" in active_clients[recipient]:
        client_socket = active_clients[recipient]["socket"]

        try:
            full_message = f"{sender}: {message}".encode("utf-8")
            client_socket.send(full_message)
            print(f"Message from {sender} to {recipient} delivered.")

        except Exception as e:
            print(f"Failed to send message from {sender} to {recipient}: {e}")

    else:
        if recipient not in messages:
            pending_messages[recipient] = []
        pending_messages[recipient].append((sender, message))
        save_pending_messages(
            PENDING_MESSAGES_FILE_PATH, recipient, sender, pending_messages
        )
        print(
            f"Message from {sender} to {recipient} saved as a pending message by the server."
        )

    # add a check here for users that are not registered on the server


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

    try:
        print(f"Connected with {address}")

        """Login protocols."""

        while True:
            # get login credentials from the client
            credentials = connection.recv(1024).decode().strip().split(",")
            username, password, existing = (
                credentials[0],
                credentials[1],
                credentials[2],
            )
            accounts = load_accounts(FILE_PATH)

            try:
                if existing == "no":
                    if username in accounts:
                        connection.send(
                            "Username already exists. Please try again.\n".encode(
                                "utf-8"
                            )
                        )  # bug here i need to fix
                    else:
                        create_account(
                            username, password, FILE_PATH
                        )  # create_account does all the checking for us
                        connection.send(
                            "Account created! You are now logged in.\n".encode("utf-8")
                        )
                        break

                elif existing == "yes":
                    # checks if the password is correctly authenticated
                    if (
                        username in accounts
                        and password == accounts[username]["password"]
                    ):
                        connection.send(
                            "Success! You are now logged in.\n".encode("utf-8")
                        )
                        break

                    else:
                        connection.send(
                            "Invalid username/password. Please try again.\n".encode(
                                "utf-8"
                            )
                        )
                        continue

            except ValueError as e:
                connection.send(
                    f"Account creation failed: {e}. Please try again.\n".encode("utf-8")
                )
                continue

        # update the active clients dictionary with the new username. this gets updated no matter what, so i am putting it outside the conditional
        active_clients[username] = {"socket": connection}
        print(f"{username} has connected.\n")

        """This section allows you to handle pending messages for offline clients."""
        # any pending messages get sent to the client first
        pending_messages = load_pending_messages(
            PENDING_MESSAGES_FILE_PATH
        )  # update the dictionary with message population info

        if username in pending_messages:
            message_list = pending_messages[username]
            num_pending_messages = len(message_list)
            message_limit = message_list[-10:]  # grabs the most recent 10 messages

            pending_message_info = (
                f"You have {num_pending_messages} pending messages:\n"
            )
            for sender, message in message_limit:
                full_message = f"{sender}: {message}\n"
                pending_message_info += full_message

                # save the message to all_messages_ever.txt for server records
                create_message(sender, username, message, messages)

            save_messages(MESSAGES_FILE_PATH, messages)
            print("Sending:", pending_message_info)
            connection.send(pending_message_info.encode("utf-8"))

            if len(message_list) > 10:
                pending_messages[username] = message_list[
                    :-10
                ]  # the next 10 messages are queued up for the client to request if they want to see more

            else:
                delete_pending_messages(PENDING_MESSAGES_FILE_PATH, username, 10)

            print(f"Pending messages for {username} sent to {username}.")
        else:
            connection.send("You have 0 pending messages.\n".encode("utf-8"))

        """The bulk of incoming messages are processed in this loop. Here, you have options to handle special keyboard commands!"""

        while True:
            # read the incoming message, make a decision of what operation to perform based on the contents of the message
            raw_message = connection.recv(1024).decode().strip()
            if not raw_message:
                break

            # protocol for special commands, like delete and list
            elif raw_message.lower() == "delete_account":
                delete_account(username, FILE_PATH)
                print(f"Account deletion requested by user {username}")
                connection.send("Account deleted successfully.".encode("utf-8"))
                break

            # signals the server to list all accounts
            elif raw_message.lower() == "list_accounts":
                print(f"List requested by user {username}")
                all_clients = list_accounts(FILE_PATH)
                connection.send(all_clients.encode("utf-8"))
                continue

            # protocol for deleting an account
            elif raw_message.lower().startswith("delete account"):
                _, message_content = raw_message.split(" ", 1)
                # delete_message(message_content, MESSAGES_FILE_PATH)
                if delete_message(
                    message_content, MESSAGES_FILE_PATH
                ):  # if deletion was successful
                    connection.send(
                        f"Message with content '{message_content}' deleted successfully.".encode(
                            "utf-8"
                        )
                    )
                    print("Message deleted from chatlog.")
                else:
                    connection.send(
                        f"Message with content '{message_content}' not found.".encode(
                            "utf-8"
                        )
                    )
                continue

            # signals if the user wants to request more than the first 10 pending messages. the username argument is the RECIEVER of the pending messages, hence the different argument name from the function definition
            elif raw_message.lower() == "more":
                if username in pending_messages and pending_messages[username]:
                    message_list = pending_messages[username]
                    if message_list:
                        message_limit = message_list[-10:]
                        more_message_info = ""
                        for sender, message in message_limit:
                            full_message = f"{sender}: {message}\n"
                            more_message_info += full_message
                        connection.send(more_message_info.encode("utf-8"))

                        # save the 10 message chunk to all_messages_ever.txt for server records. then, delete this batch from the .txt file
                        create_message(sender, username, message, messages)
                        save_messages(MESSAGES_FILE_PATH, messages)
                        pending_messages[username] = message_list[:-10]
                        delete_pending_messages(
                            PENDING_MESSAGES_FILE_PATH, username, 10
                        )

                        if not pending_messages[username]:
                            #
                            connection.send("No more messages.\n".encode("utf-8"))
                            continue
                    else:
                        connection.send("No more messages.\n".encode("utf-8"))
                        continue
                else:
                    connection.send("No more messages.\n".encode("utf-8"))
                    continue

            elif raw_message.lower() == "done":
                continue

            # all other messages
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
                    # connection.send("Invalid recipient. Please enter a valid username.".encode('utf-8'))

    except Exception as e:
        print(f"Errors: {e}")

    finally:
        connection.close()
        # if username in active_clients:
        #     del active_clients[username]
        print(f"{username} has disconnected")


def start_server():
    """Responsible for booting up the server.

    This will run until the server encounters an exception or is manually shut off. Here, the server listens for a client who wishes to connect, then starts a thread for that client.
    This ensures that we can have multiple clients running together, all on separate threads.

    """

    # grab some globals at the very beginning on boot up. this holds information we need to keep on the server, like all the message and account data
    global pending_messages  # everyone should be able to access this
    load_pending_messages(PENDING_MESSAGES_FILE_PATH)
    print("Pending messages loaded...")

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )  # this line guarantees that we can reuse the same port over and over again without having to change the number
        # server_socket.bind(('0.0.0.0', 12345)) #listen on all network interfaces. if we actually text, we uncomment this line
        server_socket.bind(("localhost", 12345))
        server_socket.listen()
        print("Server is listening...")

        while True:
            try:
                client_socket, addr = server_socket.accept()
                thread = threading.Thread(
                    target=client_handler, args=(client_socket, addr)
                )  # in order to have multiple clients, i might model each of them as a thread. results pending on if this is a smart move or not
                thread.start()
            except Exception as e:
                print(f"Fatal error {e} with server")

    finally:
        # on server shutdown, save any messages that might still be pending, and close the socket
        try:
            save_pending_messages(PENDING_MESSAGES_FILE_PATH, pending_messages)
            print("Pending messages saved...")
            server_socket.close()
        except Exception as e:
            print(f"Failed to close server socket properly! : {e}")


if __name__ == "__main__":
    FILE_PATH = "all_accounts_ever.txt"
    MESSAGES_FILE_PATH = "all_messages_ever.txt"
    PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
    active_clients = (
        {}
    )  # map of all active client usernames to their sockets. this is a universal map, which i like. i hesitate to hardcode anything though
    messages = (
        {}
    )  # dict of all messages sent through, with relevant user and reciever data
    pending_messages = {}  # same format as messages, these are just pending
    start_server()
