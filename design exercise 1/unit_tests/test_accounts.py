import unittest
import os, sys
import tempfile
import random
import string

sys.path.append("../")  #for local testing 
from accounts import *



class TestAccountManager(unittest.TestCase):
    """This is a suite of tests designed to really attack accounts.py.
    Each test sets up a temporary file before the test, and then its removed afterwards.
    """

    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile(delete=False)
        self.test_file_path = self.test_file.name
        self.test_file.close()
        self.accounts = {}



    def tearDown(self):
        """This will get rid of the file after testing."""
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)



    def generate_random_string(self, length=8):
        """Generate a random string of fixed length. This will be used for the username and password and allows
        for test isolation. Also makes sure there is no bias in the usernames we choose.
        """
        letters = string.ascii_lowercase
        return "".join(random.choice(letters) for i in range(length))



    def test_create_account(self):
        """Make sure we can create the dummy account and add it to the file."""

        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            create_account(username, password, self.test_file_path)

            # load accounts to verify the account was created
            accounts = load_accounts(self.test_file_path)

            # verify this has the structure we expect
            self.assertIsNotNone(accounts)
            self.assertIn(username, accounts)
            account = accounts[username]
            self.assertEqual(account["username"], username)
            self.assertEqual(account["password"], password)  



    def test_duplicate_username(self):
        """Makes sure that we handle dupes properly,"""
    
        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            create_account(username, password, self.test_file_path)

            #creates a new account with the same info; we should trigger the value error here
            with self.assertRaises(ValueError) as context:
                create_account(username, password, self.test_file_path)  



    def test_delete_account(self):
        """Test account deletion."""

        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            create_account(username, password, self.test_file_path)
            accounts = load_accounts(self.test_file_path)
            account = accounts[username]
            result = delete_account(username, self.test_file_path)

            #ensures that this is actually deleted - we should return False because that account is gone
            self.assertFalse(result)  
            accounts = load_accounts(self.test_file_path)

            #checks that the deleted account is no longer in the registered accounts
            self.assertNotIn(username, accounts)  



    def test_invalid_account(self):
        """Test the validation of account structures."""

        for _ in range(5):
            invalid_account = {"username": "user", "uuid": "someuuid"}
            self.assertFalse(is_valid_account(invalid_account))



    def test_list_accounts(self):
        """Test listing of accounts."""

        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            create_account(username, password, self.test_file_path)

        #make sure that SOMETHING gets written (format checked in other tests, so no need to do that here)
        accounts = list_accounts(self.test_file_path)
        self.assertIsNotNone(accounts)
        self.assertGreater(len(accounts), 0)  




class CustomTestRunner(unittest.TextTestRunner):
    """This is the package's custom test runner class. Increasing the verbosity gives you more information about the tests that were run. 
    I personally put it on 2 because I like having information but not being overwhelmed.
    """

    def __init__(self, *args, **kwargs):
        """Initialize."""

        super().__init__(*args, **kwargs)



    def run(self, test):
        """Customization for verbosity and other fun things."""

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
    """Run da tests."""

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAccountManager)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)
