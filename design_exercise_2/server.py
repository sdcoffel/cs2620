# -----------------------------------------------------------------
# SERVER STUFF - NEEDS TO BE RUN FIRST BEFORE THE CLIENT SIM STARTS 
# -----------------------------------------------------------------

"""
Server Script for Client Simulation

This script implements a simple server that facilitates messaging between multiple clients.
It handles client connections, maintains a global registry of active clients, and routes messages
from one client to another via a queue mechanism. Each connected client has its own thread for
receiving queued messages and a dedicated function for processing incoming messages.

Usage:
    Run this script first to start the server before launching the client simulation.
    The server listens on all available interfaces at port 50051.

Dependencies:
    - socket: for network communication.
    - threading: for handling multiple client connections concurrently.
    - queue: for managing message queues for each client.
"""

import socket
import threading
import queue

# Global dict to keep track of active clients.
# Client is stored as: username -> {'conn': socket, 'queue': Queue()}
active_clients = {}


def SendMessage(sender, recipient, message):
    """
    Sends a message from sender to recipient.

    This function enqueues the message into the recipient's message queue if the recipient is online.
    It logs the sending event and returns a status string indicating that the message was delivered.

    Args:
        sender (str): The username of the client sending the message.
        recipient (str): The username of the target client.
        message (str): The message content to be delivered.

    Returns:
        str: A status message indicating the result of the message delivery.
    """
    # Enqueue the message into the recipient's message queue.
    active_clients[recipient]['queue'].put((sender, message))
    # Log the event of messaging.
    print(f"{sender} is messaging {recipient}.")
    return "Message delivered."


def ReceiveMessages(username):
    """
    Continuously sends queued messages to the client.

    This function runs in its own thread for each connected client. It retrieves messages from the client's
    message queue, formats them, and sends them over the client's socket connection. In case of an error
    during sending (e.g., if the connection fails), it logs the error and breaks out of the loop.

    Args:
        username (str): The username of the client whose messages are to be sent.

    Returns:
        None
    """
    # Retrieve the client's message queue and socket connection.
    client_queue = active_clients[username]['queue']
    conn = active_clients[username]['conn']
    while True:
        try:
            sender, msg = client_queue.get()#timeout here? 
            #message formatting
            formatted_msg = f"{sender}: {msg}\n"
            # Send the formatted message over the socket.
            conn.sendall(formatted_msg.encode('utf-8'))
        except queue.Empty:
            # If the queue is empty, simply continue waiting for messages.
            continue
        except Exception as e:
            # Log any errors encountered during message sending.
            print(f"Error sending message to {username}: {e}")
            break


def handle_client(conn, addr):
    """
    Handles an individual client connection.

    This function manages the initial handshake with a new client by receiving the client's username.
    It then registers the client in the global active_clients dictionary with its own message queue,
    starts a background thread to continuously send queued messages to the client (via ReceiveMessages),
    and processes incoming messages in real time. Incoming messages must be in the format "recipient::message".
    If the format is invalid, an error message is sent back to the client.

    Args:
        conn (socket.socket): The socket object representing the client's connection.
        addr (tuple): The address of the connected client (IP address, port).

    Returns:
        None
    """
    # Log the new connection.
    print(f"New connection from {addr}")
    username = None
    try:
        #the first message from the client must be the username.
        username = conn.recv(1024).decode('utf-8').strip().lower()
        if not username:
            conn.close()
            return

        # Add the client to active_clients with its own message queue and start a thread for continuous messaging.
        active_clients[username] = {'conn': conn, 'queue': queue.Queue()}
        print(f"Client {username} has connected.")
        threading.Thread(target=ReceiveMessages, args=(username,), daemon=True).start()

        # Process messages in real time.
        while True:
            data = conn.recv(1024)
            if not data:
                break  
            #messages must be in the format "recipient::message"
            message = data.decode('utf-8').strip()
            if "::" not in message:
                conn.sendall("Invalid message format. Something got messed up on the wire.\n".encode('utf-8'))
                continue

            # Split the message into recipient and message parts.
            recipient, msg = message.split("::", 1)
            recipient = recipient.strip().lower()  #fix the whitespace issue 
            msg = msg.strip()

            # Send the message using the SendMessage function.
            response = SendMessage(username, recipient, msg)
            if response != "Message delivered successfully.":
                conn.sendall((response + "\n").encode('utf-8'))
    
    except Exception as e:
        # Log any exceptions that occur during client handling.
        print(f"Error with client {addr}: {e}")
    
    finally:
        # Clean up by removing the client from active_clients if present.
        if username and username in active_clients:
            del active_clients[username]
        # Close the client connection.
        conn.close()
        print(f"Connection from {addr} closed.")


def start_server():
    """
    Starts the server to accept and handle client connections.

    This function initializes a TCP/IP server socket that listens on all available interfaces at port 50051.
    It continuously accepts new client connections and spawns a new thread for each client using handle_client.
    The server runs indefinitely until a KeyboardInterrupt (Ctrl+C) is detected, at which point it shuts down gracefully.

    Returns:
        None
    """
    host = "0.0.0.0"  # Bind to all available network interfaces.
    port = 50051     # Port number for the server.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a TCP/IP socket.
    server.bind((host, port))  # Bind the socket to the host and port.
    server.listen()  # Start listening for incoming connections.
    print(f"Server listening on port {port}")

    try:
        while True:
            # Accept a new client connection.
            conn, addr = server.accept()
            # Start a new thread to handle this client connection.
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        # Gracefully handle a keyboard interrupt (Ctrl+C) to shut down the server.
        print("Server shutting down...")
    finally:
        # Ensure the server socket is closed before exiting.
        server.close()

if __name__ == "__main__":
    # Start the server when this script is executed directly.
    start_server()
