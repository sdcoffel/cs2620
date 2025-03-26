#this is going to be run separately to add the new server to the configuration on my laptop 

from concurrent import futures 
from accounts import *
from messages import *
from multiprocessing import Manager
from server_management_functions import *

#GLOBALS - DO NOT MOVE
FILE_PATH = "all_accounts_ever.txt"
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
pending_messages = {}


#main driver function vroom vroom 
if __name__ == "__main__":
    """Call all globally scoped variables, and start up the server. This script interfaces with the main server scripts and allows 
    for the addition of new servers to the cluster hosted at 10.250.84.166 (savanna's laptop). Just type 'add' and provide a reasonable server name and desired port.

    The loop will check to make sure that the new server isn't already in the cluster, and will notify all other servers of the new server's existence.
    """

    #load in all globals
    FILE_PATH 
    PENDING_MESSAGES_FILE_PATH
    active_clients 
    pending_messages

    manager = Manager()
    global_leader = manager.Value("global_leader", "server1")
    dynamically_added_servers = []
    # #each server must be run as a separate process in order to prevent a single point of failure 
    # #global states like pending messages and accoutnts are shared across processes and decouples the states from the server instances
    processes = []


    #option for adding in additional servers during runtime - for extra credit and running on multiple machines, per our design 
    try:
        while True:
            command = input("Enter 'add' to add a new server: \n").strip().lower()
            if command == "add":
                new_server_id = input("Enter new server ID: ").strip()
                new_server_port = int(input("Enter new server port: ").strip())
                new_server_address = f"10.250.84.166:{new_server_port}"

                # Check if server name or port is already in use
                if is_server_name_or_port_in_use(new_server_id, new_server_port):
                    print(f"Error: Server ID '{new_server_id}' or port {new_server_port} is already in use.")
                    continue

                #register the new server in ZooKeeper and notify all other servers
                register_new_server(new_server_id, new_server_address)
                notify_existing_servers(new_server_id, new_server_address)

                #fire up new server
                p = start_new_server(new_server_id, new_server_address, new_server_port, global_leader)
                processes.append(p)

                dynamically_added_servers.append(new_server_id)

            elif command == "exit":
                break
    
    finally:
        #cleanup dynamically added servers
        cleanup_dynamically_added_servers(dynamically_added_servers)
        terminate_dynamically_added_servers(processes, dynamically_added_servers)

        #terminate everyone 
        for p in processes:
            if p.is_alive():
                p.terminate()
                print("Terminated process.")

        print("Server cluster shut down.")

    for p in processes:
        p.join()


