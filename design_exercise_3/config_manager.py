from kazoo.client import KazooClient

ZOOKEEPER_HOSTS = "127.0.0.1:2181" #i assume this hosts all the server at this ip address


class ConfigManager:
    def __init__(self):
        self.zk = KazooClient(hosts=ZOOKEEPER_HOSTS)
        self.zk.start()

    def register_server(self, server_id, address):
        path = f"/servers/{server_id}"
        if not self.zk.exists(path):
            self.zk.create(path, address.encode("utf-8"))
        else:
            self.zk.set(path, address.encode("utf-8"))

    def get_all_servers(self):
        servers = {}
        if self.zk.exists("/servers"):
            for server_id in self.zk.get_children("/servers"):
                address, _ = self.zk.get(f"/servers/{server_id}")
                servers[server_id] = address.decode("utf-8")
        return servers

    def close(self):
        self.zk.stop()
        self.zk.close()