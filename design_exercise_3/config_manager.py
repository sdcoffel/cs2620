from kazoo.client import KazooClient

ZOOKEEPER_HOSTS = "127.0.0.1:2181"  # i assume this hosts all the server at this ip address


class ConfigManager:
    """
    Manages server configurations in Zookeeper using the Kazoo client.
    """

    def __init__(self):
        """
        Initialize the ConfigManager, create a KazooClient instance with
        ZOOKEEPER_HOSTS, and start the Zookeeper connection.
        """
        self.zk = KazooClient(hosts=ZOOKEEPER_HOSTS)  # Create the KazooClient
        self.zk.start()  # Start the connection to Zookeeper

    def register_server(self, server_id, address):
        """
        Register or update a server entry in Zookeeper under /servers/{server_id}.

        :param server_id: A unique identifier for the server.
        :type server_id: str
        :param address: The server's address or any other info to store.
        :type address: str
        """
        path = f"/servers/{server_id}"  # Zookeeper path for this server
        if not self.zk.exists(path):
            # If the node does not exist, create it with the address
            self.zk.create(path, address.encode("utf-8"))
        else:
            # If the node exists, update its data with the new address
            self.zk.set(path, address.encode("utf-8"))

    def get_all_servers(self):
        """
        Retrieve all servers registered under /servers.

        :return: A dictionary of server_id -> address.
        :rtype: dict
        """
        servers = {}  # Dictionary to hold all server_id -> address
        if self.zk.exists("/servers"):
            # If /servers exists, get all children (i.e., server IDs)
            for server_id in self.zk.get_children("/servers"):
                # Retrieve data for each server node
                address, _ = self.zk.get(f"/servers/{server_id}")
                servers[server_id] = address.decode("utf-8")  # Decode and store address
        return servers

    def close(self):
        """
        Stop and close the Zookeeper connection.
        """
        self.zk.stop()  # Stop the KazooClient
        self.zk.close()  # Close the connection