#this will contain serialization and deserialization functions 

#we'll see if i want to keep using "|" to separate them. for now should be ok if its one long string
def serialize_account(account):
    """Convert an account dictionary to a string."""
    return f"{account['uuid']}|{account['username']}|{account['hashed_password']}\n"


def deserialize_account(account_str):
    """Convert a string back into an account dictionary."""
    uuid, username, hashed_password = account_str.strip().split('|')
    return {
        "uuid": uuid,
        "username": username,
        "hashed_password": hashed_password
    }
