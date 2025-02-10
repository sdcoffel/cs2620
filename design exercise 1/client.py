# TODO:
# - if i start the client before the server, the connection is refused. i should have a mechanism that continuously polls the server until it's online
import socket
import threading
import hashlib
import re
import json  # <-- Added for JSON handling if JSON_MODE is True

from settings import JSON_MODE


class Client:

    def __init__(self):
        """
        Initialize the client.
        """
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
        """This function is in charge of receiving messages that have been forwarded from the server.

        Args:
            None

        Returns:
            Will return with an exception if the connection between the server and the client goes down. Else will continue until either the client or server
            terminates the connection.
        """

        try:
            message = self.client_socket.recv(4096).decode("utf-8")
            if not message:
                print("\nServer closed the connection.")
                return ""

            if JSON_MODE:
                try:
                    data = json.loads(message)
                    # If the server sends a message with a "sender" field:
                    if "sender" in data and "message" in data:
                        print(
                            f"\rReceived from {data['sender']}: {data['message']}\nYou: ",
                            end="",
                        )
                    # If the server sends some generic data response:
                    elif "data" in data:
                        print("\r" + data["data"] + "\nYou: ", end="")
                    # If the server sends pending messages or any other structured data:
                    elif "type" in data and data["type"] == "pending_messages":
                        # data might have "messages" or "count"
                        pending_str = ""
                        if "count" in data:
                            pending_str += (
                                f"You have {data['count']} pending messages:\n"
                            )
                        if "messages" in data:
                            for msg_obj in data["messages"]:
                                if "sender" in msg_obj and "message" in msg_obj:
                                    pending_str += (
                                        f"{msg_obj['sender']}: {msg_obj['message']}\n"
                                    )
                        print("\r" + pending_str + "\nYou: ", end="")
                    else:
                        # If there's some other JSON structure not handled above:
                        print("\r" + str(data) + "\nYou: ", end="")
                except json.JSONDecodeError:
                    # If for some reason we failed to parse JSON, fallback to raw print
                    print("\rReceived: " + message + "\nYou: ", end="")
            else:
                # Original non-JSON mode
                print("\rReceived: " + message + "\nYou: ", end="")
            return message
        except:
            print("\nServer closed the connection.")
            return ""

    def send_messages(self, recipient, message):
        """Sends messages along the socket to the server. If an empty message is typed, the user has the power to
        terminate the connection when prompted. Different error handling mechanisms are at the bottom of the function.
        The user can exit the chat by typing 'quit', change the intended recipient by typing 'change', or delete a message that was sent during that session by typing 'delete'.

        Args:
            recipient (str): The recipient username
            message (str): The message content
        """
        full_message = f"{recipient}:{message}"
        if JSON_MODE:
            data_to_send = {"raw_message": full_message}
            self.client_socket.send(json.dumps(data_to_send).encode("utf-8"))
        else:
            self.client_socket.send(full_message.encode("utf-8"))

    def delete_message(self, message):
        """Sends a request to delete a message from the server.

        Args:
            message (str): The content (or partial content) of the message to be deleted.
        """
        if JSON_MODE:
            data_to_send = {"raw_message": "delete " + message}
            self.client_socket.send(json.dumps(data_to_send).encode("utf-8"))
            server_message = self.client_socket.recv(1024).decode("utf-8")
            print(server_message)
        else:
            self.client_socket.send(("delete" + message).encode("utf-8"))
            server_message = self.client_socket.recv(1024).decode("utf-8")
            print(server_message)

    def handle_login(self, username, password, existing):
        """Handles the login process for the client. This prompts the user for their login data, and sends it to the server for credential validation.
        If the user has any pending messages, these are handled at login and displayed for the client to see in bunches of 10 messages. The client can request to see another 10 messages
        at a time if they wish to see more.

        Args:
            username (str): The username to log in with
            password (str): The password to log in with
            existing (str): "yes" or "no", indicating if the account already exists
        """
        hashed_password = self.hash_password(password)  # hashes the password

        if JSON_MODE:
            login_data = {
                "username": username,
                "password": hashed_password,
                "existing": existing,
            }
            self.client_socket.send(json.dumps(login_data).encode("utf-8"))
        else:
            credentials = f"{username},{hashed_password},{existing}"
            self.client_socket.send(credentials.encode("utf-8"))

        # wait for server confirmation to validate credentials
        server_message = self.client_socket.recv(1024).decode("utf-8")
        if JSON_MODE:
            try:
                response = json.loads(server_message)
                if "data" in response:
                    print(response["data"])
                    server_message = response["data"]
                else:
                    print(server_message)
            except json.JSONDecodeError:
                # fallback if somehow not JSON
                print(server_message)
        else:
            print(server_message)

        self.username = username
        return server_message

    def get_pending_messages(self):
        """Grab any pending messages after login. The server automatically sends these right after login.

        Returns:
            A string representation (in non-JSON mode) or the raw string from the server if not JSON,
            or a textual summary if in JSON mode.
        """
        pending_message_info = self.client_socket.recv(4096).decode("utf-8")
        if JSON_MODE:
            try:
                data = json.loads(pending_message_info)
                # Could be a "data" or "type":"pending_messages"
                if "data" in data:
                    print(data["data"])
                elif "type" in data and data["type"] == "pending_messages":
                    pending_str = ""
                    if "count" in data:
                        pending_str += f"You have {data['count']} pending messages:\n"
                    if "messages" in data:
                        for msg_obj in data["messages"]:
                            if "sender" in msg_obj and "message" in msg_obj:
                                pending_str += (
                                    f"{msg_obj['sender']}: {msg_obj['message']}\n"
                                )
                    print(pending_str)
                else:
                    # Fallback
                    print(pending_message_info)
            except json.JSONDecodeError:
                # fallback to raw text
                print(pending_message_info)
        else:
            print(pending_message_info)
        return pending_message_info

    def grab_more_messages(self):
        """Requests more messages from the server if the user wants to see the next batch of 10.

        Returns:
            The server's response, either JSON or plain text.
        """
        if JSON_MODE:
            self.client_socket.send(json.dumps({"raw_message": "more"}).encode("utf-8"))
            more_messages = self.client_socket.recv(4096).decode("utf-8")
            try:
                data = json.loads(more_messages)
                # Could be "type":"pending_messages" or "data" for "No more messages."
                if "data" in data:
                    return data["data"]
                elif "type" in data and data["type"] == "pending_messages":
                    pending_str = ""
                    if "messages" in data:
                        for msg_obj in data["messages"]:
                            if "sender" in msg_obj and "message" in msg_obj:
                                pending_str += (
                                    f"{msg_obj['sender']}: {msg_obj['message']}\n"
                                )
                    return pending_str
                else:
                    return more_messages
            except json.JSONDecodeError:
                return more_messages
        else:
            self.client_socket.send("more".encode("utf-8"))
            more_messages = self.client_socket.recv(4096).decode("utf-8")
            return more_messages

    def delete_account(self):
        """Sends a request to the server to delete the user's account.

        Returns:
            The server message response (plain text or JSON).
        """
        if JSON_MODE:
            self.client_socket.send(
                json.dumps({"raw_message": "delete_account"}).encode("utf-8")
            )
            server_message = self.client_socket.recv(1024).decode("utf-8")
            if server_message:
                try:
                    data = json.loads(server_message)
                    if "data" in data:
                        print(data["data"])
                        return data["data"]
                    else:
                        print(server_message)
                        return server_message
                except json.JSONDecodeError:
                    print(server_message)
                    return server_message
            return server_message
        else:
            self.client_socket.send("delete_account".encode("utf-8"))
            server_message = self.client_socket.recv(1024).decode("utf-8")
            print(server_message)
            return server_message

    def confirm_deletion(self, server_message, confirmation):
        """Handles the confirmation step when the server notifies the user they have unread messages
        and asks if they're sure about deleting the account.

        Args:
            server_message (str): The server's initial message (which may mention unread messages).
            confirmation (str): The user's response ("yes" or "no").

        Returns:
            The server response after confirmation.
        """
        if "You have unread messages" in server_message:
            if JSON_MODE:
                # The server asked for confirmation
                self.client_socket.send(
                    json.dumps({"raw_message": confirmation}).encode("utf-8")
                )
                server_message = self.client_socket.recv(1024).decode("utf-8")
                try:
                    data = json.loads(server_message)
                    if "data" in data:
                        return data["data"]
                    return server_message
                except json.JSONDecodeError:
                    return server_message
            else:
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
        if JSON_MODE:
            self.client_socket.send(
                json.dumps({"raw_message": "list_accounts"}).encode("utf-8")
            )
            server_message = self.client_socket.recv(4096).decode("utf-8")
            try:
                data = json.loads(server_message)
                if "data" in data:
                    # Could be a list or single string
                    if isinstance(data["data"], list):
                        return data["data"]
                    else:
                        return [data["data"]]
                else:
                    return [server_message]
            except json.JSONDecodeError:
                return [server_message]
        else:
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
            filtered_accounts = [
                account for account in accounts if re.search(pattern, account)
            ]

        if not filtered_accounts:
            return "No accounts match the given pattern."

        return filtered_accounts

    def set_recipient(self, recipient):
        """Sets the intended recipient for future messages.

        Args:
            recipient (str): The username of the recipient.
        """
        if JSON_MODE:
            data_to_send = {"raw_message": recipient}
            self.client_socket.send(json.dumps(data_to_send).encode("utf-8"))
        else:
            self.client_socket.send(recipient.encode("utf-8"))

    def start_client(self, host, port):
        """Responsible for booting up the client and establishing the first connection to the server. Connects to the server on a localhost port.

        Args:
            host (str): The server IP or hostname
            port (int): The server port
        """
        self.client_socket.connect((host, port))
        self.connected = True
        print("Connected to the server.")
