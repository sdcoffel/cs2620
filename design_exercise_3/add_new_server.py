#this is going to be run separately to add the new server to the configuration on my laptop 
import grpc 
import time 
import multiprocessing
import chatapp_pb2
import chatapp_pb2_grpc
from concurrent import futures 
from accounts import *
from messages import *
from multiprocessing import Manager
from raftnode import RaftNode, RaftService
from chatserver import ChatServer
from config_manager import ConfigManager
from zookeeper_manager import ZooKeeperManager

#GLOBALS - DO NOT MOVE
FILE_PATH = "all_accounts_ever.txt"
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
pending_messages = {}



##############################Server Management and Stuff##########################################
def is_server_name_or_port_in_use(server_id, port):
    """
    Check if a server name or port is already in use.
    
    Args:
        server_id (str): The server ID to check
        port (int): The port number to check
        
    Returns:
        bool: True if either the server ID or port is already in use, False otherwise
    """
    zk_manager = ZooKeeperManager()
    try:
        # Check if server ID already exists
        if zk_manager.zk.exists(f"/servers/{server_id}"):
            return True
            
        # Check if port is already in use by another server
        existing_servers = zk_manager.list_children("/servers")
        for existing_id in existing_servers:
            server_address = zk_manager.get_znode(f"/servers/{existing_id}")
            if f":{port}" in server_address:  # Check if port appears in address
                return True
                
        return False
    finally:
        zk_manager.close()

def register_new_server(server_id, address):
    zk_manager = ZooKeeperManager()
    path = f"/servers/{server_id}"
    if zk_manager.zk.exists(path):
        print(f"zNode at {path} already exists. Updating its value.")
        zk_manager.update_znode(path, address)
    else:
        zk_manager.create_znode(path, address)
        print(f"Server {server_id} registered in ZooKeeper with address {address}.")
    zk_manager.close()


def notify_existing_servers(new_server_id, new_server_address):
    zk_manager = ZooKeeperManager()
    try:
        existing_servers = zk_manager.list_children("/servers")

        for server_id in existing_servers:
            if server_id != new_server_id:  # Don't notify the new server about itself
                try:
                    server_address = zk_manager.get_znode(f"/servers/{server_id}")
                    with grpc.insecure_channel(server_address) as channel:
                        stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                        request = chatapp_pb2.AddServerRequest(server_id=new_server_id, address=new_server_address)
                        response = stub.AddServer(request)
                        print(f"Notified {server_id} about new server {new_server_id}: {response.success}")
                except Exception as e:
                    print(f"Failed to notify {server_id} about new server: {e}")
                    print(f"Retrying notification to {server_id}...")
                    time.sleep(2)  #delay before retrying
                    try:
                        with grpc.insecure_channel(server_address) as channel:
                            stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                            request = chatapp_pb2.AddServerRequest(server_id=new_server_id, address=new_server_address)
                            response = stub.AddServer(request)
                            print(f"Retry successful: Notified {server_id} about new server {new_server_id}: {response.success}")
                    except Exception as retry_exception:
                        print(f"Retry failed: Could not notify {server_id} about new server: {retry_exception}")
    finally:
        zk_manager.close()



def start_new_server(server_id, address, port, global_leader):
    """Start a new server instance."""
    p = multiprocessing.Process(target=run_server_instance, args=(port, server_id, global_leader))
    p.start()
    print(f"New server {server_id} started on {address}:{port}.")
    time.sleep(2) #delay to ensure that the new server properly starts up - probably don't need this 
    return p



#######for cleaning up the servers added during runtime to prevent synchronization issues##################
def cleanup_dynamically_added_servers(dynamically_added_servers):
    """Remove dynamically added servers from ZooKeeper."""
    zk_manager = ZooKeeperManager()
    for server_id in dynamically_added_servers:
        path = f"/servers/{server_id}"
        if zk_manager.zk.exists(path):
            zk_manager.zk.delete(path)
            print(f"Removed zNode for {server_id} from ZooKeeper.")
    zk_manager.close()


def terminate_dynamically_added_servers(processes, dynamically_added_servers):
    """Terminate processes for dynamically added servers."""
    for server_id in dynamically_added_servers:
        for process in processes:
            if process.is_alive():
                process.terminate()
                print(f"Terminated process for {server_id}.")



def start_server(port, server_id):
    """Boots up and runs the gRPC server until termination.
    This function:
      - Loads any pending messages from persistent storage.
      - Creates a gRPC server using a ThreadPoolExecutor with up to 10 worker threads.
      - Registers the ChatServiceServicer (i.e., ChatServer) with the gRPC server.
      - Binds the server to port 50051 and starts it.
      - Calls wait_for_termination() to block execution until a termination signal (e.g., KeyboardInterrupt) is received.

    Upon termination (Cntrl+C for us), the function attempts to save any pending messages back to persistent storage before exiting.

    Returns:
        None
    """

    #persistent storage
    global pending_messages
    global raft_node
    load_pending_messages(PENDING_MESSAGES_FILE_PATH) #upload from persistent storage
    
    try:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        chatapp_pb2_grpc.add_ChatServiceServicer_to_server(ChatServer(), server)
        chatapp_pb2_grpc.add_RaftServiceServicer_to_server(RaftService(raft_node), server)
        server.add_insecure_port(f'0.0.0.0:{port}')
        server.start()
        print(f"{server_id} is listening on port {port}...")
        server.wait_for_termination() #this is a blocking call that keeps the server running until keyboard interrupt

    except Exception as e: 
        print(f"Fatal error {e} with server")


def run_server_instance(port, server_id, global_leader):
    global raft_node
    address = f"10.250.84.166:{port}" #this lets anyone on another machine look for my laptops ip address and request to connect

    #each server instance gets its own raftnode
    raft_node = RaftNode(server_id=server_id, peers=[], address = address, timeout=5, global_leader=global_leader) #default to starting with no peers which can be added in
    start_server(port, server_id)


#main driver function vroom vroom 
if __name__ == "__main__":
    """Call all globally scoped variables, and start up the server. Server 1 is designated as the leader by default, and we always start with 
    three replicas on my machine to ensure 2 fault tolerance. To maintian multiple servers across multiple machines, you can either add additional servers during runtime,
    or immediately start three more replicas on another machine and connect them to the same ZooKeeper instance.
    
    Each server is its own process with global states such as the designated cluster leader shared across all processes. We maintain persistent storage by immediatly 
    saving pending messages to disk in the ChatServer class. If a server, or even the entire cluster goes down, we can always recover those messages.
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


