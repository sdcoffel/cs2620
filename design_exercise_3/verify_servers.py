#helper script that lets us check which servers are active on my laptop
# Helper script that lets us check and manage active servers on my laptop
from kazoo.client import KazooClient

ZOOKEEPER_HOSTS = "10.250.84.166:2181"

zk = KazooClient(hosts=ZOOKEEPER_HOSTS)
zk.start()

# List the children of the /servers zNode
if zk.exists("/servers"):
    children = zk.get_children("/servers")
    if children:
        print("All active servers and their IP addresses:")
        for child in children:
            path = f"/servers/{child}"
            if zk.exists(path):
                # Retrieve the data stored in the zNode (e.g., IP:port)
                data, _ = zk.get(path)
                print(f"Server ID: {child}, Address: {data.decode('utf-8')}")
    else:
        print("No servers are currently registered in ZooKeeper.")
else:
    print("No servers active. The /servers zNode does not exist.")

# Option to manually remove a server
if zk.exists("/servers"):
    server_to_remove = input("Enter the server ID to remove (or press Enter to skip): ").strip()
    if server_to_remove:
        path = f"/servers/{server_to_remove}"
        if zk.exists(path):
            zk.delete(path)
            print(f"Removed server '{server_to_remove}' from ZooKeeper.")
        else:
            print(f"Server '{server_to_remove}' does not exist in ZooKeeper.")

zk.stop()