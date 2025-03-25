import multiprocessing
from concurrent import futures 
from accounts import *
from messages import *
from multiprocessing import Manager
from server_management_functions import *


#todo: graceful error management when the remote servers go down 

#GLOBALS - DO NOT MOVE
FILE_PATH = "all_accounts_ever.txt"
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
pending_messages = {}



# main driver function vroom vroom
if __name__ == "__main__":
    """
    Call all globally scoped variables, and start up the server. Server 1 is designated as the leader by default,
    and we always start with three replicas on the local machine to ensure up to two nodes can fail (2-fault tolerance).
    To maintain multiple servers across multiple machines, you can either add additional servers at runtime,
    or immediately start three or more replicas on another machine and connect them to the same ZooKeeper instance.

    Each server is its own process with global states, such as the designated cluster leader shared across processes.
    We maintain persistent storage by saving pending messages to disk in the ChatServer class. If a server, or even the
    entire cluster goes down, we can always recover those messages.

    Typing "exit" will terminate the cluster and clean up resources in ZooKeeper.
    """

    # Load in all globals
    FILE_PATH 
    PENDING_MESSAGES_FILE_PATH
    active_clients 
    pending_messages

    # Manager for shared data among processes (e.g., global_leader)
    manager = Manager()
    global_leader = manager.Value("global_leader", "server1")

    # For 2-fault tolerance, we need at least 3 servers. By default, we start with 3 servers on this machine.
    ports = [50051, 50052, 50053]
    server_ids = ["server1", "server2", "server3"]  # Default to three servers on startup

    dynamically_added_servers = []

    # Each server must be run as a separate process to prevent a single point of failure
    processes = []
    for port, server_id in zip(ports, server_ids):
        p = multiprocessing.Process(target=run_server_instance, args=(port, server_id, global_leader))
        p.start()
        processes.append(p)
    
    # Optionally add additional servers during runtime
    try:
        while True:
            print("Server cluster is live.")
            command = input("Enter 'exit' to shut down the cluster. \n").strip().lower()

            if command == "exit":
                break
    
    finally:
        # Clean up dynamically added servers in ZooKeeper
        cleanup_dynamically_added_servers(dynamically_added_servers)

        # Terminate all dynamically added server processes
        terminate_dynamically_added_servers(processes, dynamically_added_servers)

        # Terminate all remaining processes
        for p in processes:
            if p.is_alive():
                p.terminate()
                print("Terminated process.")

        print("Server cluster shut down.")

    # Ensure all processes exit cleanly
    for p in processes:
        p.join()




