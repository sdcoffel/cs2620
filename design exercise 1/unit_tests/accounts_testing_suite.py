import unittest 
from unittest.mock import patch, MagicMock
import os, sys
import tempfile
import random
import string
sys.path.append('/Users/savannacoffel/cs2620/design exercise 1')
from accounts import create_account, load_accounts, save_accounts, delete_account, list_accounts, is_valid_account


class TestAccountManager(unittest.TestCase): 
    """This is a suite of tests designed to really attack accounts.py.
        Each test sets up a temporary file before the test, and then its removed afterwards.

    """
    
    def setUp(self): 
        self.test_file = tempfile.NamedTemporaryFile(delete=False)
        self.test_file_path = self.test_file.name
        self.test_file.close()

    def tearDown(self): 
        """This will get rid of the file after testing."""
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)


    def generate_random_string(self, length=8):
        """Generate a random string of fixed length. This will be used for the username and password and allows 
        for test isolation. Also makes sure there is no bias in the usernames we choose
        
        """
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(length))


    def test_create_account(self):
        
        """Make sure we can create the dummy account and add it to the file"""
        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            account = create_account(username, password)

            # assertions we NEED to pass
            self.assertTrue(is_valid_account(account))
            self.assertEqual(account['username'], username) # we better pass these
            self.assertNotEqual(account['hashed_password'], password) # checks that the hashing algo did something

            # make sure account gets saved
            accounts = load_accounts()
            self.assertIn(account['uuid'], accounts)

    
    def test_duplicate_username(self):
        """Makes sure that we handle dupes properly"""
        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            create_account(username, password)

            with self.assertRaises(ValueError) as context:
                create_account(username, password) # creates a new account with the same info; we should trigger the value error here
                

    def test_delete_account(self):
        """Test account deletion"""
        for _ in range(5):
            username = self.generate_random_string()
            password = self.generate_random_string()
            account = create_account(username, password)
            result = delete_account(account['uuid'])
            self.assertTrue(result) # ensures that this is actually deleted
            accounts = load_accounts()
            self.assertNotIn(account['uuid'], accounts) # checks that the deleted account is no longer in the registered accounts


      
    def test_invalid_account(self):
        """Test the validation of account structures"""
        for _ in range(5):
            invalid_account = {"username": "user", "uuid": "someuuid"}
            self.assertFalse(is_valid_account(invalid_account))




class CustomTestRunner(unittest.TextTestRunner):
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



if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAccountManager)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)
