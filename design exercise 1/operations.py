# this will contain serialization and deserialization functions used to save accounts and messages 

def serialize_account(account):
    """Serialize an account dictionary into a line for the accounts file."""
    return f"{account['uuid']}|{account['username']}|{account['password']}\n"


def deserialize_account(line):
    """Deserialize a line from the accounts file into an account dictionary."""
    uuid, username, password = line.strip().split("|")
    return {"uuid": uuid, "username": username, "password": password}
