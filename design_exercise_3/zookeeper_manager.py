from kazoo.client import KazooClient

ZOOKEEPER_HOSTS = "10.250.84.166:2181"  

class ZooKeeperManager:
    def __init__(self):
        try:
            self.zk = KazooClient(hosts=ZOOKEEPER_HOSTS)
            self.zk.start()
        except Exception as e:
            print(f"Error connecting to ZooKeeper: {e}")
            raise

    def create_znode(self, path, value):
        """Create a zNode in ZooKeeper."""
        try:
            # Ensure parent zNodes exist
            parent_path = "/".join(path.split("/")[:-1])
            if parent_path and not self.zk.exists(parent_path):
                self.zk.ensure_path(parent_path)  # Create parent zNodes if they don't exist

            # Create the zNode
            if not self.zk.exists(path):
                self.zk.create(path, value.encode("utf-8"))
                print(f"Created zNode at {path} with value: {value}")
            else:
                print(f"zNode at {path} already exists.")
        except Exception as e:
            print(f"Error creating zNode at {path}: {e}")
            raise

    def update_znode(self, path, value):
        """Update the value of an existing zNode."""
        if self.zk.exists(path):
            self.zk.set(path, value.encode("utf-8"))
            print(f"Updated zNode at {path} with value: {value}")
        else:
            print(f"zNode at {path} does not exist.")

    def get_znode(self, path):
        """Retrieve the value of a zNode."""
        if self.zk.exists(path):
            value, _ = self.zk.get(path)
            return value.decode("utf-8")
        else:
            print(f"zNode at {path} does not exist.")
            return None

    def list_children(self, path):
        """List the children of a zNode."""
        if self.zk.exists(path):
            return self.zk.get_children(path)
        else:
            print(f"zNode at {path} does not exist.")
            return []

    def delete_znode(self, path):
        """Delete a zNode."""
        if self.zk.exists(path):
            self.zk.delete(path, recursive=True)
            print(f"Deleted zNode at {path}.")
        else:
            print(f"zNode at {path} does not exist.")

    def close(self):
        """Close the ZooKeeper connection."""
        self.zk.stop()
        self.zk.close()