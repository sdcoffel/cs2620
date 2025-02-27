import socket
import threading
import random
import queue
import time
import os

def receive_messages(sock, net_queue):
    """
    Continuously receives messages from the server and enqueues them
    in net_queue.
    """
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                net_queue.put("Server disconnected.")
                break
            #add the message to the client's queue
            net_queue.put(data.decode('utf-8').strip())
        except Exception as e:
            net_queue.put("Error receiving message: " + str(e))
            break

def process_network_queue(net_queue, clock_rate, clock, log_file):
    """
    Processes messages from the network queue at intervals defined by the
    clock rate (ticks per second). This simulates the machine's internal
    processing at its own clock speed.
    """
    tick_interval = 1.0 / clock_rate
    while True:
        time.sleep(tick_interval)  # Wait for the next tick.
        clock["value"] += 1  # Increment logical clock.
        while not net_queue.empty():
            message = net_queue.get()
            log_msg = f"[Clock {clock['value']}] Received: {message}"
            print("\n" + log_msg + "\nYou: ", end="", flush=True)
            log_file.write(log_msg + "\n")
            log_file.flush()


def start_client():
    host = input("Enter server host: ")
    port = int(input("Enter server port: "))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    #the first message is the username
    username = input("Enter your username: ").strip()
    sock.send(username.encode('utf-8'))
    print(f"Connected to the server as {username}.")

    #clock rate
    clock_rate = random.randint(1, 6)
    print(f"Clock rate is: {clock_rate} ticks per second.")

    #a logical clock container - gets incremented by +1 every time network queue gets processed or we send a message
    clock = {"value": 0}
    print(f"Logical clock set.")

    #open the log file 
    log_file = open(f"log_{username}.txt", "a")
    print("Log file opened.")

    #set recipeient
    default_recipient = input("Enter recipient: ").strip()
    print(f"Default recipient set to {default_recipient}")

    #create a network queue for incoming messages.
    net_queue = queue.Queue()

    #start thread to listen for messages and process the queue
    threading.Thread(target=receive_messages, args=(sock, net_queue), daemon=True).start()
    threading.Thread(target=process_network_queue, args=(net_queue, clock_rate, clock, log_file), daemon=True).start() #once per clock tick 

    #main processing loop for sending messages.
    while True:
        if default_recipient:
            message = input("You: ")
            if not message:
                continue
            msg_to_send = f"{default_recipient}::{message}"
        else:
            recipient = input("Enter recipient: ").strip()
            message = input("Enter message: ")
            msg_to_send = f"{recipient}::{message}"
        try:
            sock.send(msg_to_send.encode('utf-8'))
            #update clock and write to log 
            clock["value"] += 1
            send_log = f"[Clock {clock['value']}] Sent: {msg_to_send}"
            print(send_log)
            log_file.write(send_log + "\n")
            log_file.flush()

        except Exception as e:
            print("Error sending message:", e)
            break


if __name__ == "__main__":
    start_client()

