import os
import bcrypt
import uuid
from operations import *


def load_accounts(FILE_PATH):
    """Load the accounts dictionary from a text file. The password must be the already hashed password.

    Returns:
        dict: A dictionary of accounts loaded from the txtfile.
              If the file does not exist, returns an empty dictionary.
    """
    accounts = {}
    try:
        with open(FILE_PATH, "r") as f:
            for line in f:
                account = deserialize_account(line)
                accounts[account["username"]] = account
    except FileNotFoundError:
        print("No accounts file found, starting with an empty dictionary")
    return accounts


def save_accounts(accounts, FILE_PATH):
    """Save the given dictionary of accounts to a serialized form.

    Args:
        accounts (dict): The dictionary of account objects to be saved.
    """
    with open(FILE_PATH, "w") as f:
        for account in accounts.values():
            f.write(serialize_account(account))


def is_valid_account(account):
    """Check if the given account dictionary is valid.

    This function loads the current accounts from the file (as required),
    though the loaded accounts are not used in validation.

    Args:
        account (dict): A dictionary representing an account.

    Returns:
        bool: True if `account` is valid (i.e., contains 'uuid', 'username',
              and 'hashed_password'), False otherwise.
    """
    required_keys = {"uuid", "username", "hashed_password"}
    if not isinstance(account, dict):
        return False
    return set(account.keys()) == required_keys


def create_account(username, password, FILE_PATH):
    """Create a new account and save it to the txt file.

    This function loads existing accounts from the file, checks for duplicate
    usernames, generates a new UUID for the account, and validates the new
    account structure.

    Args:
        username (str): The username of the new account.
        password (str): The user-supplied password of the new account.
        When we create the account, we use bcrypt to hash the password.

    Returns:
        dict: The newly created account object.

    Raises:
        ValueError: If the username already exists or if the new account is invalid.
    """
    accounts = load_accounts(FILE_PATH)

    if username in accounts:
        raise ValueError("Username already exists")
    account = {
        "uuid": str(uuid.uuid4()),
        "username": username,
        "password": password #fix this later
    }
    accounts[username] = account
    save_accounts(accounts, FILE_PATH)


def delete_account(username, FILE_PATH):
    """Delete an account by UUID and save the update to the txt file.

    Args:
        account_uuid (str): The UUID of the account to delete.

    Returns:
        bool: True if the account was found and deleted, False otherwise.
    """
    accounts = load_accounts(FILE_PATH)
    if username not in accounts:
        raise ValueError("Username does not exist")
    del accounts[username]
    save_accounts(accounts, FILE_PATH)


def list_accounts(FILE_PATH):
    """List all accounts currently stored.

    Returns:
        list: A list of all account objects. I modified this so that every entry is on a new line, for readability
    """
    # TODO list accounts by wildcard
    accounts = load_accounts(FILE_PATH)
    return "\n".join(accounts.keys())


# if __name__ == '__main__':
#     FILE_PATH = "accounts.txt"

#     my_account = create_account(username, password) #update this to automatically parse into strings so that we don't have to
#     test = list_accounts()
#     print(test)
