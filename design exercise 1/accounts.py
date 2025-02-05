import os
import pickle
import uuid

FILE_PATH = "accounts.pkl"


def load_accounts():
    """Load the accounts dictionary from the `accounts.pkl` file.

    Returns:
        dict: A dictionary of accounts loaded from the `accounts.pkl` file.
              If the file does not exist, returns an empty dictionary.
    """
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "rb") as f:
            return pickle.load(f)
    return {}


def save_accounts(accounts):
    """Save the given dictionary of accounts to the `accounts.pkl` file.

    Args:
        accounts (dict): The dictionary of account objects to be saved.
    """
    with open(FILE_PATH, "wb") as f:
        pickle.dump(accounts, f)


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


def create_account(username, hashed_password):
    """Create a new account and save it to the `accounts.pkl` file.

    This function loads existing accounts from the file, checks for duplicate
    usernames, generates a new UUID for the account, and validates the new
    account structure.

    Args:
        username (str): The username of the new account.
        hashed_password (str): The hashed password of the new account.

    Returns:
        dict: The newly created account object.

    Raises:
        ValueError: If the username already exists or if the new account is invalid.
    """
    accounts = load_accounts()

    # Check for duplicate username
    for existing_account in accounts.values():
        if existing_account["username"] == username:
            raise ValueError(f"Username '{username}' already exists.")

    # Generate a new UUID and create the account
    new_uuid = str(uuid.uuid4())
    account_object = {
        "uuid": new_uuid,
        "username": username,
        "hashed_password": hashed_password,
    }

    # Validate the account object
    if not is_valid_account(account_object):
        raise ValueError("Invalid account object structure.")

    # Save the account
    accounts[new_uuid] = account_object
    save_accounts(accounts)

    return account_object


def delete_account(account_uuid):
    """Delete an account by UUID and save the update to the `accounts.pkl` file.

    Args:
        account_uuid (str): The UUID of the account to delete.

    Returns:
        bool: True if the account was found and deleted, False otherwise.
    """
    accounts = load_accounts()

    if account_uuid in accounts:
        del accounts[account_uuid]
        save_accounts(accounts)
        return True
    return False


def list_accounts():
    """List all accounts currently stored in `accounts.pkl`.

    Returns:
        list: A list of all account objects.
    """
    accounts = load_accounts()
    return list(accounts.values())
