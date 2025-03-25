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


#todo, put the heartbeat at 10ms
#todo, put the election timeout at 150ms
#todo, put the append entries timeout at 50ms

#todo: after i get this working, move server management functions into a separate script

#GLOBALS - DO NOT MOVE
FILE_PATH = "all_accounts_ever.txt"
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
pending_messages = {}


##############################Server Management and Stuff##########################################

def register_new_server(server_id, address):
    """
    Registers or updates a server's information in ZooKeeper.

    If the specified zNode path already exists, its value (the server address) is updated.
    Otherwise, a new zNode is created. After the update or creation, the ZooKeeper connection is closed.

    Args:
        server_id (str): The unique identifier for the server (e.g., 'server1').
        address (str): The server's network address (e.g., '10.250.84.166:50051').
    """
    zk_manager = ZooKeeperManager()
    path = f"/servers/{server_id}"

    # Check if a zNode for this server already exists
    if zk_manager.zk.exists(path):
        print(f"zNode at {path} already exists. Updating its value.")
        zk_manager.update_znode(path, address)
    else:
        zk_manager.create_znode(path, address)
        print(f"Server {server_id} registered in ZooKeeper with address {address}.")
    zk_manager.close()


def notify_existing_servers(new_server_id, new_server_address):
    """
    Notifies existing servers about a newly added server.

    Attempts to contact each server currently registered under /servers in ZooKeeper,
    informing them of the new server via an AddServer RPC call. If the call fails, it retries once.

    Args:
        new_server_id (str): The unique identifier of the new server (e.g., 'server4').
        new_server_address (str): The network address of the new server.
    """
    zk_manager = ZooKeeperManager()

    try:
        # Retrieve a list of all existing server IDs
        existing_servers = zk_manager.list_children("/servers")

        # Notify each existing server about the new server, except the new server itself
        for server_id in existing_servers:
            if server_id != new_server_id:  # Don't self-notify
                try:
                    server_address = zk_manager.get_znode(f"/servers/{server_id}")
                    print(f"Test to notify {server_id} about new server {new_server_id} at {server_address}")
                    with grpc.insecure_channel(server_address) as channel:
                        stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                        request = chatapp_pb2.AddServerRequest(server_id=new_server_id, address=new_server_address)
                        response = stub.AddServer(request)
                        print(f"Notified {server_id} about new server {new_server_id}: {response.success}")
                except Exception as e:
                    print(f"Failed to notify {server_id} about new server: {e}")
                    print(f"Retrying notification to {server_id}...")
                    time.sleep(2)  # Delay before retrying
                    try:
                        with grpc.insecure_channel(server_address) as channel:
                            stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                            request = chatapp_pb2.AddServerRequest(server_id=new_server_id, address=new_server_address)
                            response = stub.AddServer(request)
                            print(f"Retry successful: Notified {server_id} about new server {new_server_id}: {response.success}")
                    except Exception as retry_exception:
                        print(f"Retry failed: Could not notify {server_id} about new server: {retry_exception}")
    finally:
        # Make sure to close the ZooKeeper connection
        zk_manager.close()


def start_new_server(server_id, address, port, global_leader):
    """
    Start a new server instance as a separate process.

    This function launches a new process running 'run_server_instance', which will
    initialize and start a gRPC server. The process is returned after a short delay
    to ensure the new server is fully started.

    Args:
        server_id (str): Unique identifier for the new server.
        address (str): IP address or hostname for the new server.
        port (int): Port on which the new server will listen.
        global_leader (multiprocessing.managers.Value): A shared variable denoting the cluster leader.

    Returns:
        multiprocessing.Process: The process object representing the new server instance.
    """
    # Create a new process that runs our server code
    p = multiprocessing.Process(target=run_server_instance, args=(port, server_id, global_leader))
    p.start()  # Start the new process
    print(f"New server {server_id} started on {address}:{port}.")
    time.sleep(2)  # Delay to ensure that the new server properly starts up
    return p


def cleanup_dynamically_added_servers(dynamically_added_servers):
    """
    Remove dynamically added servers from ZooKeeper.

    This is typically called when the program is shutting down or exiting,
    ensuring that server zNodes added during runtime are cleaned up.

    Args:
        dynamically_added_servers (list): List of server IDs that were added dynamically.
    """
    zk_manager = ZooKeeperManager()

    # For each dynamically added server, delete its corresponding zNode from ZooKeeper
    for server_id in dynamically_added_servers:
        path = f"/servers/{server_id}"
        if zk_manager.zk.exists(path):
            zk_manager.zk.delete(path)
            print(f"Removed zNode for {server_id} from ZooKeeper.")
    zk_manager.close()


def terminate_dynamically_added_servers(processes, dynamically_added_servers):
    """
    Terminate processes associated with dynamically added servers.

    Loops through all active processes and terminates those that correspond to
    servers in 'dynamically_added_servers'.

    Args:
        processes (list): A list of multiprocessing.Process objects representing running servers.
        dynamically_added_servers (list): List of dynamically added server IDs.
    """
    # For each dynamically added server, try to find its corresponding process and terminate it
    for server_id in dynamically_added_servers:
        for process in processes:
            if process.is_alive():
                process.terminate()
                print(f"Terminated process for {server_id}.")


def start_server(port, server_id):
    """
    Boots up and runs the gRPC server until termination.

    This function:
      - Loads any pending messages from persistent storage.
      - Creates a gRPC server using a ThreadPoolExecutor with up to 10 worker threads.
      - Registers the ChatServiceServicer (i.e., ChatServer) with the gRPC server.
      - Registers the RaftServiceServicer (i.e., RaftService) with the gRPC server.
      - Binds the server to the specified port and starts it.
      - Calls wait_for_termination() to block execution until a termination signal is received.

    Upon termination, the function attempts to save any pending messages back to
    persistent storage before exiting.

    Args:
        port (int): The port on which the server will be listening.
        server_id (str): The unique identifier for this server instance.

    Returns:
        None
    """
    # persistent storage
    global pending_messages
    global raft_node

    # Load any stored pending messages from file
    load_pending_messages(PENDING_MESSAGES_FILE_PATH)  # upload from persistent storage
    
    try:
        # Create a gRPC server with a pool of threads to handle requests
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

        # Add our custom ChatServer service
        chatapp_pb2_grpc.add_ChatServiceServicer_to_server(ChatServer(), server)

        # Add the Raft service to handle Raft-specific RPC calls
        chatapp_pb2_grpc.add_RaftServiceServicer_to_server(RaftService(raft_node), server)

        # Bind the server to the specified port
        server.add_insecure_port(f'0.0.0.0:{port}')
        server.start()

        print(f"{server_id} is listening on port {port}...")

        # This call blocks until the server is terminated
        server.wait_for_termination()
    except Exception as e:
        # Catch any fatal errors
        print(f"Fatal error {e} with server")


def run_server_instance(port, server_id, global_leader):
    """
    Function run in a separate process to start an individual server instance.

    Creates and initializes a RaftNode (with the provided server_id, address, etc.)
    and then starts the gRPC server by calling start_server.

    Args:
        port (int): The port on which this server instance will listen.
        server_id (str): The unique identifier for this server (e.g., 'server1').
        global_leader (multiprocessing.managers.Value): A shared variable denoting the cluster leader.

    Returns:
        None
    """
    global raft_node
    # Construct the address string using the given port
    address = f"10.250.84.166:{port}"

    # Each server instance gets its own RaftNode
    # The global_leader variable is shared, but the node itself is unique to this process
    raft_node = RaftNode(
        server_id=server_id,
        peers=[],
        address=address,
        timeout=5,
        global_leader=global_leader
    )
    start_server(port, server_id)


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

    This script also provides an interactive prompt for adding new servers during runtime via the "add" command.
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




