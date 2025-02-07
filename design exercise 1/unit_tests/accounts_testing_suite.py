import unittest
from unittest.mock import patch, MagicMock
import os, sys
import tempfile
import random
import string

# Import the "accounts" module and any functions you still directly use
# (create_account, delete_account, etc.)
sys.path.append("../")  # i really shouldn't hardcode this lol
import accounts
from accounts import (
    create_account,
    delete_account,
    list_accounts,
    is_valid_account,
)


class TestAccountManager(unittest.TestCase):
    """This is a suite of tests designed to really attack accounts.py.
    Each test sets up a temporary SQLite database file before the test,
    and then it's removed afterwards.
    """

    def setUp(self):
        # Create a temp file to act as our SQLite database
        self.test_file = tempfile.NamedTemporaryFile(delete=False)
        self.test_file_path = self.test_file.name
        self.test_file.close()

        # Override the DB_PATH in the accounts module to point to our temp file
        accounts.DB_PATH = self.test_file_path

        # Initialize the table schema in the new database
        accounts.initialize_db()

    def tearDown(self):
        """Remove the temporary SQLite file after testing."""
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def generate_random_string(self, length=8):
        """Generate a random string of fixed length. This will be used for the
        username and password and allows for test isolation.
        """
        letters = string.ascii_lowercase
        return "".join(random.choice(letters) for _ in range(length))

    def load_accounts(self):
        """
        This local helper mimics the old load_accounts() logic by
        querying the SQLite database directly and returning a dictionary
        of {uuid: account_dict}.
        """
        with accounts.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT uuid, username, hashed_password FROM accounts")
            rows = cursor.fetchall()

        accs = {}
        for acc_uuid, acc_username, acc_hashed in rows:
            accs[acc_uuid] = {
                "uuid": acc_uuid,
                "username": acc_username,
                "hashed_password": acc_hashed,
            }
        return accs

    def test_create_account(self):
        """Make sure we can create a dummy account and add it to the DB."""
        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            account = create_account(username, password)

            # Assertions we need to pass
            self.assertTrue(is_valid_account(account))
            self.assertEqual(account["username"], username)
            self.assertNotEqual(
                account["hashed_password"], password
            )  # Ensure hashing changed the password

            # Make sure account gets saved
            accounts_dict = self.load_accounts()
            self.assertIn(account["uuid"], accounts_dict)

    def test_duplicate_username(self):
        """Make sure that we handle duplicate usernames properly."""
        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            create_account(username, password)

            with self.assertRaises(ValueError):
                create_account(username, password)  # same username, should fail

    def test_delete_account(self):
        """Test account deletion."""
        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            account = create_account(username, password)
            result = delete_account(account["uuid"])
            self.assertTrue(result)

            # Check that the deleted account is no longer in the DB
            accounts_dict = self.load_accounts()
            self.assertNotIn(account["uuid"], accounts_dict)

    def test_invalid_account(self):
        """Test the validation of account structures."""
        for _ in range(5):
            invalid_account = {"username": "user", "uuid": "someuuid"}
            self.assertFalse(is_valid_account(invalid_account))


class CustomTestRunner(unittest.TextTestRunner):
    """This is the package's custom test runner class. You can customize
    the output of the test results however you want.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, test):
        result = super().run(test)
        print("\n\nTest Summary")
        print("-------------------")
        print(f"{result.testsRun} tests run in total.")
        if not result.wasSuccessful():
            print(f"{len(result.failures) + len(result.errors)} tests failed.")
        else:
            print("All tests passed!")
        return result


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAccountManager)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)
