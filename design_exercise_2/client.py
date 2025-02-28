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
    Continuously receives messages from the server and enqueues them.
    """
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                net_queue.put("Server disconnected.")
                break
            net_queue.put(data.decode('utf-8').strip())
        
        except Exception as e:
            net_queue.put("Error receiving message: " + str(e))
            break


def process_network_queue(net_queue, clock_rate, clock, log_file, sock, other_recipients):
    """
    On each clock tick, if there's a message in the network queue, remove one,
    update the logical clock, and log the event. Otherwise, generate a random event.
    """
    tick_interval = 1.0 / clock_rate
    while True:
        time.sleep(tick_interval)
        clock["value"] += 1  #clock gets incremented by 1 
        global_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        
        #if there is at least one message in the queue, we update the log. clock, and write relevant info to the log
        if not net_queue.empty():
            message = net_queue.get()
            queue_length = net_queue.qsize()
            log_msg = (f"[Clock {clock['value']}] Received: {message} | Global time: {global_time} "
                       f"| Queue length: {queue_length} | Logical clock: {clock['value']}")
            print(f"{log_msg}\n", flush=True)
            log_file.write(log_msg + "\n")
            log_file.flush()
       
       #otherwise, the queue is empty, so simulate a random number between 1-10:
        else:
            rand_val = random.randint(1, 10)
            #if value is 1, send to machine b all the relevant info 
            if rand_val == 1:
                msg = f"Logical clock time: {clock['value']}"
                try:
                    sock.send(f"{other_recipients[0]}::{msg}".encode('utf-8'))
                    clock["value"] += 1
                    log_msg = (f"[Clock {clock['value']}] Sent to {other_recipients[0]}: {msg} | Global time: {global_time} "
                               f"| Logical clock: {clock['value']}")
                    print(f"{log_msg}\n", flush=True)
                    log_file.write(log_msg + "\n")
                    log_file.flush()
                except Exception as e:
                    print("Error sending message:", e)
            
            #if value is 2, send to machine c all the relevant info 
            elif rand_val == 2:
                recipient = other_recipients[1] if len(other_recipients) > 1 else other_recipients[0]
                msg = f"Logical clock time: {clock['value']}"
                try:
                    sock.send(f"{recipient}::{msg}".encode('utf-8'))
                    clock["value"] += 1
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
                for recipient in other_recipients:
                    try:
                        sock.send(f"{recipient}::{msg}".encode('utf-8'))
                    except Exception as e:
                        print("Error sending message to", recipient, ":", e)
                clock["value"] += 1
                log_msg = (f"[Clock {clock['value']}] Sent to {', '.join(other_recipients)}: {msg} | Global time: {global_time} "
                           f"| Logical clock: {clock['value']}")
                print(f"{log_msg}\n", flush=True)
                log_file.write(log_msg + "\n")
                log_file.flush()
            
            #otherwise, log this as an internal event, and log all relevant values 
            else:
                log_msg = (f"[Clock {clock['value']}] Internal event occurred. | Global time: {global_time} "
                           f"| Logical clock: {clock['value']}")
                print(f"{log_msg}\n", flush=True)
                log_file.write(log_msg + "\n")
                log_file.flush()


def simulate_client(username, host, port, simulation_duration):
    """
    Simulate a client with a given username that automatically connects,
    sends its username as the first message, preloads its network queue,
    and runs the simulation autonomously for simulation_duration seconds.
    """
    #this will keep track of the other recipients so the server correctly maps messages 
    all_clients = ['a', 'b', 'c']
    username = username.lower()
    other_recipients = [x for x in all_clients if x != username]
    print(f"[{username}] Other machine recipients: {other_recipients}")

    #create the socket and connect to the server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    #server expects username as the first message - so immediately send it over when the client is active
    sock.send(username.encode('utf-8'))
    print(f"[{username}] Connected to the server.")

    #get clock rate
    clock_rate = random.randint(1, 6)
    print(f"[{username}] Clock rate is: {clock_rate} ticks per second.")
    
    #lamport clocks and log files 
    clock = {"value": 0}
    log_file = open(f"log_{username}.txt", "a")
    print(f"[{username}] Log file opened.")

    #create a network queue and prepopulate it with test messages -- this simulates the clients 'talking' to each other
    net_queue = queue.Queue()
    num_preloaded = random.randint(2, 4)
    for i in range(num_preloaded):
        sender = random.choice(other_recipients)
        test_message = f"{sender} -> {username}: Preloaded message {i+1}"
        net_queue.put(test_message)
    print(f"[{username}] Preloaded {num_preloaded} messages into the network queue.")

    #recieving/processing messages get their own threads
    threading.Thread(target=receive_messages, args=(sock, net_queue), daemon=True).start()
    threading.Thread(target=process_network_queue, 
                     args=(net_queue, clock_rate, clock, log_file, sock, other_recipients),
                     daemon=True).start()

    #run simulation for this long
    time.sleep(simulation_duration)
    
    #log and close connections
    end_msg = f"[{username}] Simulation ended after {simulation_duration} seconds."
    print(end_msg)
    log_file.write(end_msg + "\n")
    log_file.flush()
    sock.close()
    log_file.close()
    os._exit(0)  #force exit

# -------------------------------
# DRIVERRRRR CODEEEEEEE (for sim)
# -------------------------------
if __name__ == "__main__":
    #usernames as command-line arguments; if none, default to a, b, c. you need to supply 'python client.py a b c'
    if len(sys.argv) < 2:
        usernames = ['a', 'b', 'c']
    else:
        usernames = [arg.strip().lower() for arg in sys.argv[1:]]
    
    #host and port prompts
    host = input("Enter server host: ").strip()
    port = int(input("Enter server port: ").strip())
    
    simulation_duration = 30  #go for 30 seconds - tweakable
    
    #each registered username (client), spawns a thread to simulate their interactions 
    threads = []
    for username in usernames:
        t = threading.Thread(target=simulate_client, args=(username, host, port, simulation_duration))
        t.daemon = True
        t.start()
        threads.append(t)
    
    #wait until all threads are done before ending the simulation
    for t in threads:
        t.join()
