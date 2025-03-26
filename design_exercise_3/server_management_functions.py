#this is going to be run separately to add the new server to the configuration on my laptop 
import grpc 
import time 
import multiprocessing
import chatapp_pb2
import chatapp_pb2_grpc
from concurrent import futures 
from accounts import *
from messages import *
from raftnode import RaftNode, RaftService
from chatserver import ChatServer
from zookeeper_manager import ZooKeeperManager
PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"


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
        print(f"Checking if server ID '{server_id}' or port {port} is already in use...")
        
        # Check if /servers path exists
        if not zk_manager.zk.exists("/servers"):
            print("'/servers' path doesn't exist in ZooKeeper yet. Creating it...")
            zk_manager.zk.ensure_path("/servers")
            return False
            
        # Check if server ID already exists
        server_path = f"/servers/{server_id}"
        server_exists = zk_manager.zk.exists(server_path)
        if server_exists:
            print(f"Server ID '{server_id}' already exists in ZooKeeper at {server_path}")
            return True
            
        # Check if port is already in use by another server
        existing_servers = zk_manager.list_children("/servers")
        print(f"Found {len(existing_servers)} existing servers: {existing_servers}")
        
        for existing_id in existing_servers:
            server_path = f"/servers/{existing_id}"
            server_address = zk_manager.get_znode(server_path)
            print(f"Server {existing_id} has address: '{server_address}'")
            port_str = f":{port}"
            if server_address and port_str in server_address:
                print(f"Port {port} is already in use by server {existing_id}")
                return True
                
        print(f"Server ID '{server_id}' and port {port} are available for use")
        return False
    except Exception as e:
        print(f"Error in is_server_name_or_port_in_use: {e}")
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
            if server_id != new_server_id:  #don't notify the new server about itself
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
    address = f"10.253.131.213:{port}"  # This lets anyone on another machine look for my laptop's IP address and request to connect

    # Each server instance gets its own RaftNode
    raft_node = RaftNode(server_id=server_id, peers=[], address=address, timeout=5, global_leader=global_leader)  # Default to starting with no peers which can be added in

    # Register the server in ZooKeeper
    zk_manager = ZooKeeperManager()
    try:
        # Ensure the /servers zNode exists
        if not zk_manager.zk.exists("/servers"):
            zk_manager.zk.ensure_path("/servers")

        # Register the server as an ephemeral zNode
        zk_manager.create_znode(f"/servers/{server_id}", address)
        print(f"Server {server_id} registered in ZooKeeper with address {address}.")
    except Exception as e:
        print(f"Error registering server {server_id} in ZooKeeper: {e}")
    finally:
        zk_manager.close()

    # Start the gRPC server
    start_server(port, server_id)