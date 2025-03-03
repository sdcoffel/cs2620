"""
Client Simulation Script

This script simulates a networked client that connects to a server, sends and receives messages,
and logs events using a logical clock system (Lamport clocks). The client uses multithreading to
handle message receiving and processing concurrently. This simulation demonstrates logical clock
updates and inter-client communication by preloading messages and generating random events.

Usage:
    Run the script with command-line arguments representing the client usernames.
    If no arguments are provided, it defaults to using ['a', 'b', 'c'].
    Example: python client.py a b c

Dependencies:
    - socket
    - threading
    - random
    - queue
    - time
    - sys
    - os
"""

import socket
import threading
import random
import queue
import time
import sys
import os

# ---------------------------------
# FUNCTIONS THAT RUN DURING THE SIM 
# ---------------------------------

def receive_messages(sock, net_queue):
    """
    Continuously receives messages from the server and enqueues them into a thread-safe queue.

    This function listens for incoming data on the given socket. It decodes the data from bytes to a UTF-8
    string, strips any extra whitespace, and then places the message into the provided network queue.
    If the server disconnects (i.e., no data is received) or an exception occurs during reception,
    an appropriate error or disconnect message is enqueued and the loop terminates.

    Args:
        sock (socket.socket): The socket connected to the server used for receiving messages.
        net_queue (queue.Queue): A thread-safe queue for storing received messages.

    Returns:
        None
    """
    while True:
        try:
            # Attempt to receive data from the server (blocking call)
            data = sock.recv(1024)
            # Check if no data is received, meaning the connection has likely been closed.
            if not data:
                net_queue.put("Server disconnected.")
                break
            # Decode the received bytes into a string, strip whitespace, and add it to the network queue.
            net_queue.put(data.decode('utf-8').strip())
        
        except Exception as e:
            # On error, put error message in queue and exit the loop.
            net_queue.put("Error receiving message: " + str(e))
            break


def process_network_queue(net_queue, clock_rate, clock, log_file, sock, other_recipients):
    """
    Processes events from the network queue and simulates random events on each clock tick.

    On every clock tick (as determined by the clock_rate), this function increments the logical clock and
    records the current global time. If there is a message in the network queue, it is dequeued, and an event
    is logged that includes the message, current global time, and the logical clock value. If the queue is empty,
    a random event is simulated which may involve sending messages to one or more recipients or logging an internal event.

    Args:
        net_queue (queue.Queue): Thread-safe queue containing incoming network messages.
        clock_rate (int): Number of clock ticks per second; determines the sleep interval.
        clock (dict): A dictionary holding the logical clock value (key "value") used for event ordering.
        log_file (file object): Open file object used for logging event messages.
        sock (socket.socket): Socket used to send messages to other recipients.
        other_recipients (list of str): List of recipient identifiers (e.g., other client names) to which messages may be sent.

    Returns:
        None
    """
    tick_interval = 1.0 / clock_rate  # Calculate interval duration for each tick.
    while True:
        time.sleep(tick_interval)  # Sleep for the duration of one tick.
        clock["value"] += 1  #clock gets incremented by 1 
        # Get the current global time formatted as a string.
        global_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        
        #if there is at least one message in the queue, we update the log. clock, and write relevant info to the log
        if not net_queue.empty():
            message = net_queue.get()  # Retrieve the next message from the network queue.
            queue_length = net_queue.qsize()  # Get the current number of messages left in the queue.
            # Construct a log message including clock, global time, queue length, and message content.
            log_msg = (f"[Clock {clock['value']}] Received: {message} | Global time: {global_time} "
                       f"| Queue length: {queue_length} | Logical clock: {clock['value']}")
            print(f"{log_msg}\n", flush=True)  # Print the log message to standard output.
            log_file.write(log_msg + "\n")  # Write the log message to the log file.
            log_file.flush()  # Flush the log file buffer to ensure the message is written.
       
       #otherwise, the queue is empty, so simulate a random number between 1-10:
        else:
            rand_val = random.randint(1, 10)  # Generate a random number to determine the event.
            #if value is 1, send to machine b all the relevant info 
            if rand_val == 1:
                msg = f"Logical clock time: {clock['value']}"
                try:
                    # Send message to the first recipient in the list.
                    sock.send(f"{other_recipients[0]}::{msg}".encode('utf-8'))
                    clock["value"] += 1  # Increment logical clock after sending.
                    log_msg = (f"[Clock {clock['value']}] Sent to {other_recipients[0]}: {msg} | Global time: {global_time} "
                               f"| Logical clock: {clock['value']}")
                    print(f"{log_msg}\n", flush=True)
                    log_file.write(log_msg + "\n")
                    log_file.flush()
                except Exception as e:
                    print("Error sending message:", e)
            
            #if value is 2, send to machine c all the relevant info 
            elif rand_val == 2:
                # Select recipient based on list length: use second recipient if available, otherwise fallback to first.
                recipient = other_recipients[1] if len(other_recipients) > 1 else other_recipients[0]
                msg = f"Logical clock time: {clock['value']}"
                try:
                    # Send message to the selected recipient.
                    sock.send(f"{recipient}::{msg}".encode('utf-8'))
                    clock["value"] += 1  # Increment logical clock.
                    log_msg = (f"[Clock {clock['value']}] Sent to {recipient}: {msg} | Global time: {global_time} "
                               f"| Logical clock: {clock['value']}")
                    print(f"{log_msg}\n", flush=True)
                    log_file.write(log_msg + "\n")
                    log_file.flush()
                except Exception as e:
                    print("Error sending message:", e)
            
            #if value is 3, send to both machines all the relevant info 
            elif rand_val == 3:
                msg = f"Logical clock time: {clock['value']}"
                # Iterate over all other recipients and send the message to each.
                for recipient in other_recipients:
                    try:
                        sock.send(f"{recipient}::{msg}".encode('utf-8'))
                    except Exception as e:
                        print("Error sending message to", recipient, ":", e)
                clock["value"] += 1  # Increment logical clock after sending to all recipients.
                log_msg = (f"[Clock {clock['value']}] Sent to {', '.join(other_recipients)}: {msg} | Global time: {global_time} "
                           f"| Logical clock: {clock['value']}")
                print(f"{log_msg}\n", flush=True)
                log_file.write(log_msg + "\n")
                log_file.flush()
            
            #otherwise, log this as an internal event, and log all relevant values 
            else:
                # Log an internal event when no message is sent.
                log_msg = (f"[Clock {clock['value']}] Internal event occurred. | Global time: {global_time} "
                           f"| Logical clock: {clock['value']}")
                print(f"{log_msg}\n", flush=True)
                log_file.write(log_msg + "\n")
                log_file.flush()


def simulate_client(username, host, port, simulation_duration):
    """
    Simulates a client that connects to a server, preloads messages, and autonomously interacts for a set duration.

    The client simulation includes connecting to the server, sending the username as an initial message,
    preloading the network queue with test messages (to simulate inter-client communication), and starting
    dedicated threads for receiving and processing messages. The simulation runs for a specified duration,
    after which all connections are closed and the process is terminated.

    Args:
        username (str): The client's username which identifies the machine (should be 'a', 'b', or 'c').
        host (str): The server hostname or IP address to connect to.
        port (int): The server port number to connect to.
        simulation_duration (int): Duration in seconds for which the simulation will run.

    Returns:
        None
    """
    #this will keep track of the other recipients so the server correctly maps messages 
    all_clients = ['a', 'b', 'c']
    username = username.lower()  # Ensure username is in lowercase for consistency.
    # Determine the list of other machines by excluding the current username.
    other_recipients = [x for x in all_clients if x != username]
    print(f"[{username}] Other machine recipients: {other_recipients}")

    #create the socket and connect to the server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a TCP/IP socket.
    sock.connect((host, port))  # Connect to the server using provided host and port.
    
    #server expects username as the first message - so immediately send it over when the client is active
    sock.send(username.encode('utf-8'))  # Send username to the server.
    print(f"[{username}] Connected to the server.")

    #get clock rate
    clock_rate = random.randint(1, 6)  # Randomly determine the clock rate (ticks per second).
    print(f"[{username}] Clock rate is: {clock_rate} ticks per second.")
    
    #lamport clocks and log files 
    clock = {"value": 0}  # Initialize the logical clock with a starting value of 0.
    log_file = open(f"log_{username}.txt", "a")  # Open a log file for appending events.
    print(f"[{username}] Log file opened.")

    #create a network queue and prepopulate it with test messages -- this simulates the clients 'talking' to each other
    net_queue = queue.Queue()  # Create a thread-safe queue for network messages.
    num_preloaded = random.randint(2, 4)  # Determine a random number of preloaded messages.
    for i in range(num_preloaded):
        sender = random.choice(other_recipients)  # Randomly select a sender from the list of other recipients.
        test_message = f"{sender} -> {username}: Preloaded message {i+1}"
        net_queue.put(test_message)  # Enqueue the test message.
    print(f"[{username}] Preloaded {num_preloaded} messages into the network queue.")

    #recieving/processing messages get their own threads
    threading.Thread(target=receive_messages, args=(sock, net_queue), daemon=True).start()  # Start thread for receiving messages.
    threading.Thread(target=process_network_queue, 
                     args=(net_queue, clock_rate, clock, log_file, sock, other_recipients),
                     daemon=True).start()  # Start thread for processing the network queue.

    #run simulation for this long
    time.sleep(simulation_duration)  # Let the simulation run for the specified duration.
    
    #log and close connections
    end_msg = f"[{username}] Simulation ended after {simulation_duration} seconds."
    print(end_msg)
    log_file.write(end_msg + "\n")  # Write simulation end message to the log.
    log_file.flush()  # Flush the log file buffer.
    # sock.close()  # Close the socket connection.
    # log_file.close()  # Close the log file.
    os._exit(0)  #force exit


# -------------------------------
# DRIVERRRRR CODEEEEEEE (for sim)
# -------------------------------
if __name__ == "__main__":
    #usernames as command-line arguments; if none, default to a, b, c. you need to supply 'python client.py a b c'
    if len(sys.argv) < 2:
        usernames = ['a', 'b', 'c']
    else:
        # Use provided usernames from command-line arguments, converting them to lowercase.
        usernames = [arg.strip().lower() for arg in sys.argv[1:]]
    
    #host and port prompts
    host = input("Enter server host: ").strip()  # Prompt user for the server host.
    port = int(input("Enter server port: ").strip())  # Prompt user for the server port.
    
    simulation_duration = 30  #go for 30 seconds - tweakable
    
    #each registered username (client), spawns a thread to simulate their interactions 
    threads = []  # List to keep track of client simulation threads.
    for username in usernames:
        # Create a new thread for each simulated client.
        t = threading.Thread(target=simulate_client, args=(username, host, port, simulation_duration))
        t.daemon = True  # Set thread as daemon so it exits when main program exits.
        t.start()  # Start the client simulation thread.
        threads.append(t)  # Append thread to list.
    
    #wait until all threads are done before ending the simulation
    for t in threads:
        t.join()  # Block until the thread finishes execution.
