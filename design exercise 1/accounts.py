import os
import bcrypt
import uuid
import sqlite3
from operations import *  # Assuming this has your serialize/deserialize ops, if needed

DB_PATH = "database.db"


def get_connection():
    """
    Helper to provide a new database connection.
    """
    return sqlite3.connect(DB_PATH)


def initialize_db():
    """
    Create the accounts table if it doesn't exist.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                uuid TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                hashed_password BLOB NOT NULL
            )
            """
        )
        conn.commit()


def is_valid_account(account):
    """Check if the given account dictionary is valid.

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


def create_account(username, password):
    """Create a new account and save it to the database.

    This function checks for duplicate usernames, generates a new UUID
    for the account, and validates the new account structure.

    Args:
        username (str): The username of the new account.
        password (str): The user-supplied password of the new account.

    Returns:
        dict: The newly created account object.

    Raises:
        ValueError: If the username already exists or if the new account is invalid.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check for duplicate username
        cursor.execute("SELECT username FROM accounts WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            raise ValueError(f"Username '{username}' already exists.")

        # Generate a new UUID and create the account
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        new_uuid = str(uuid.uuid4())

        account_object = {
            "uuid": new_uuid,
            "username": username,
            "hashed_password": hashed_password,
        }

        # Validate the account object
        if not is_valid_account(account_object):
            raise ValueError("Invalid account object structure.")

        # Insert the account into the database
        cursor.execute(
            "INSERT INTO accounts (uuid, username, hashed_password) VALUES (?, ?, ?)",
            (new_uuid, username, hashed_password),
        )
        conn.commit()

    return account_object


def delete_account(account_uuid):
    """Delete an account by UUID from the database.

    Args:
        account_uuid (str): The UUID of the account to delete.

    Returns:
        bool: True if the account was found and deleted, False otherwise.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # Check if the account exists
        cursor.execute("SELECT uuid FROM accounts WHERE uuid = ?", (account_uuid,))
        row = cursor.fetchone()
        if not row:
            return False

        # Delete the account
        cursor.execute("DELETE FROM accounts WHERE uuid = ?", (account_uuid,))
        conn.commit()

    return True


def list_accounts():
    """List all accounts currently stored in the database.

    Returns:
        str: A string representation of all account objects, each on a new line.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT uuid, username, hashed_password FROM accounts")
        rows = cursor.fetchall()

    accounts = []
    for acc_uuid, acc_username, acc_hashed in rows:
        # Each row is a tuple from the DB, convert to a dict if you want that structure
        account = {
            "uuid": acc_uuid,
            "username": acc_username,
            "hashed_password": acc_hashed,
        }
        accounts.append(str(account))

    return "\n".join(accounts)


# Initialize the database table if this module is ever imported or run:
initialize_db()


# Example usage (uncomment if you want to test):
# if __name__ == '__main__':
#     username = "fillinhere"
#     password = "fillinhere"
#     my_account = create_account(username, password)
#     print(list_accounts())
