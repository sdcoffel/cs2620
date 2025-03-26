#helper script that lets us check which servers are active on my laptop
from kazoo.client import KazooClient

ZOOKEEPER_HOSTS = "10.253.131.213:2181"

zk = KazooClient(hosts=ZOOKEEPER_HOSTS)
zk.start()

# List the children of the /servers zNode
if zk.exists("/servers"):
    children = zk.get_children("/servers")
    print(f"All active servers: {children}")

    # Prompt the user to remove a server
    server_to_remove = input("Enter the server ID to remove (or press Enter to skip): ").strip()
    if server_to_remove:
        path = f"/servers/{server_to_remove}"
        if zk.exists(path):
            zk.delete(path)
            print(f"Removed server '{server_to_remove}' from ZooKeeper.")
        else:
            print(f"Server '{server_to_remove}' does not exist in ZooKeeper.")
else:
    print("No servers active.")

zk.stop()