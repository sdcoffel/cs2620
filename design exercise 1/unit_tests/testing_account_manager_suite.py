import unittest 
from unittest.mock import patch, MagicMock
import os, sys
sys.path.append('/Users/savannacoffel/cs2620/design exercise 1')
from accounts import create_account, load_accounts, save_accounts, delete_account, list_accounts, is_valid_account

#technically, my functions in accounts.py behave correctly. however, these tests lack isolation. therefore they suck. and i HAVE to fix them before moving on 

#THE ISSUE is that there is no process isolation here. you'll likely get errors if you run this multiple times telling you that a name already exists. this is because all of these 
#tests are writing to the same file, test_accounts.txt. this is an issue i need to fix. setUp and tearDown should be wiping this file after every test, but they're not for some reason. 
#pending on this. i like the format of this a lot though, and i really want it to work. 

#ian, you might have to look at this 

#basically my tests suck lololol

class TestAccountManager(unittest.TestCase): 
    """This is a suite of tests designed to really attack accounts.py.
        Each test sets up a temporary file before the test, and then its removed afterwards.
    """
    
    def setUp(self): 
        self.test_file_path = "test_accounts.txt"
        open(self.test_file_path, 'w').close() #should be empty at the beginning of each test
       
    def tearDown(self): 
        """This will get rid of the file after testing."""
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)


    def test_create_account(self): 
        """Make sure we can create the dummy account and add it to the file"""

        username = "test"
        password = "test"
        account = create_account(username, password)

        #assertions we NEED to pass
        self.assertTrue(is_valid_account(account))
        self.assertEqual(account['username'], username) #we better pass these
        self.assertNotEqual(account['hashed_password'], password) #checks that the hashing algo did something

        #make sure account gets saved
        accounts = load_accounts()
        self.assertIn(account['uuid'], accounts)

    
    def test_duplicate_username(self):
        """Makes sure that we handle dupes properly"""
        username = "test"
        password = "test"
        create_account(username, password)

        with self.assertRaises(ValueError) as context: 
            create_account(username, password) #creates a new account with the same info 
            #we should trigger the value error here
    

    def test_delete_account(self):
        """Test account deletion"""
        username = "test"
        password = "test"
        account = create_account(username, password)
        result = delete_account(account['uuid'])
        self.assertTrue(result) #ensures that this is actually deleted
        accounts = load_accounts()
        self.assertNotIn(account['uuid'], accounts) #checks that the deleted account is no longer in the registered accounts 


    def test_list_accounts(self):
        """Test listing accounts"""
        create_account("test", "test")
        create_account("test", "test")
        accounts = list_accounts()
        self.assertEqual(len(accounts), 2)



    def test_invalid_account(self):
        """Test the validation of account structures"""
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
