import unittest
from unittest.mock import mock_open, patch
import os, sys
sys.path.append('/Users/savannacoffel/cs2620/design exercise 1') #i really shouldn't hardcode this lol
from messages import *
from datetime import datetime
import tempfile
import string, random


class TestMessageManager(unittest.TestCase):
    def setUp(self):
        """Create a temporary file to simulate the message storage mechanism and prepare the environment for message operations."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file_path = self.temp_file.name
        self.temp_file.close()
        self.messages = {}


    def tearDown(self):
        """Clean up the temporary file after tests are complete."""
        os.remove(self.temp_file_path)


    def generate_random_string(self, length=10):
        """Generate a random string of fixed length"""
        letters = string.ascii_letters
        return ''.join(random.choice(letters) for i in range(length))
    

    def test_is_valid_message(self):
        """Test the validation of message structures"""
        valid_message = {
            "uuid": "1234",
            "datetime": datetime.now().isoformat(),
            "sender": "alice",
            "receiver": "bob",
            "content": "Hello, Bob!"
        }
        self.assertTrue(is_valid_message(valid_message))

        invalid_message = {
            "uuid": "1234",
            "datetime": datetime.now().isoformat(),
            "sender": "alice",
            # 'receiver' key is missing
            "content": "Hello, Bob!"
        }
        self.assertFalse(is_valid_message(invalid_message))


    def test_create_message(self):
        """Test creating a message and storing it in a dictionary"""
        sender = "alice"
        receiver = "bob"
        content = "Hello, Bob!"
        message = create_message(sender, receiver, content, self.messages)
        self.assertTrue(is_valid_message(message))
        self.assertEqual(message['sender'], sender)
        self.assertEqual(message['receiver'], receiver)
        self.assertEqual(message['content'], content)
        self.assertIn(message['uuid'], self.messages)


    def test_delete_message(self):
        """Test deleting a message by its content"""
        # First, create a message to delete
        sender = "alice"
        receiver = "bob"
        content = "Temporary message"
        message = create_message(sender, receiver, content, self.messages)
        self.assertFalse(delete_message("nonexistent message", self.temp_file_path))


    def test_list_messages(self):
        """Test listing all messages or between specific users"""
        sender = "alice"
        receiver = "bob"
        content = "Hello, Bob!"
        message = create_message(sender, receiver, content, self.messages)

        all_messages = list_messages(self.messages)
        self.assertEqual(len(all_messages), 1)
        self.assertIn(message, all_messages)

        filtered_messages = list_messages(self.messages, sender, receiver)
        self.assertEqual(len(filtered_messages), 1)
        self.assertIn(message, filtered_messages)

        # Test with no matches
        no_match_messages = list_messages(self.messages, "charlie", "dave")
        self.assertEqual(len(no_match_messages), 0)


    def test_list_messages_filtering_and_ordering(self):
        """Test filtering and ordering of listed messages"""
        sender = "alice"
        receiver = "bob"
        contents = ["Hi Bob", "Hi Alice", "How are you?", "I'm fine, thanks!"]
        for content in contents:
            create_message(sender, receiver, content, self.messages)

        # Reverse the list to simulate out-of-order insertion
        for content in reversed(contents):
            create_message(receiver, sender, content, self.messages)

        filtered_messages = list_messages(self.messages, sender, receiver)
        expected_order = contents + list(reversed(contents))
        actual_order = [msg['content'] for msg in filtered_messages]

        self.assertEqual(actual_order, expected_order)


    @patch('builtins.open', mock_open(read_data="uuid1,2020-01-01 12:00,alice,bob,Hello!\n" + "uuid2,2020-01-01 12:05,alice,charlie,Hey there!\n"))
    def test_load_messages(self):
        """Test loading messages from a file with mocked file opening to ensure proper handling of CSV formatted data."""
        # Import the function/module under test
        from messages import load_messages

        # Call the function that reads the file
        messages = load_messages('fake_path')

        # Assertions to verify that messages were loaded correctly
        self.assertEqual(len(messages), 2)
        self.assertIn('uuid1', messages)
        self.assertIn('uuid2', messages)
        self.assertEqual(messages['uuid1']['content'], 'Hello!')
        self.assertEqual(messages['uuid2']['content'], 'Hey there!')


    #THE MOTHERLOAD OF TESTING
    def test_random_message_operations(self):
        """Test creating, ordering, and loading messages with random data"""
        num_messages = 10
        senders = [self.generate_random_string() for _ in range(num_messages)]
        receivers = [self.generate_random_string() for _ in range(num_messages)]
        contents = [self.generate_random_string(20) for _ in range(num_messages)]

        # Create messages with random data
        for i in range(num_messages):
            create_message(senders[i], receivers[i], contents[i], self.messages)

        # Simulate writing to a file and then reading from it
        mock_data = ''.join(f"{msg['uuid']},{msg['datetime']},{msg['sender']},{msg['receiver']},{msg['content']}\n"
                            for msg in self.messages.values())
        
        with patch('builtins.open', mock_open(read_data=mock_data)) as mocked_file:
            loaded_messages = load_messages('fake_path')
            self.assertEqual(len(loaded_messages), num_messages)
            # Ensure all messages are loaded correctly
            for uuid, message in loaded_messages.items():
                self.assertIn(uuid, self.messages)
                self.assertEqual(message['content'], self.messages[uuid]['content'])
        
        # Test filtering and sorting messages between two specific users
        test_sender = senders[0]
        test_receiver = receivers[0]
        filtered_messages = list_messages(self.messages, test_sender, test_receiver)

        expected_contents = [msg['content'] for msg in self.messages.values() if
                             (msg['sender'] == test_sender and msg['receiver'] == test_receiver) or
                             (msg['sender'] == test_receiver and msg['receiver'] == test_sender)]

        actual_contents = [msg['content'] for msg in filtered_messages]
        self.assertEqual(sorted(expected_contents), sorted(actual_contents))



class CustomTestRunner(unittest.TextTestRunner):
    """This is the package's custom test runner class. You can customize the output of the test results 
    however you want. Increasing the verbosity gives you more information about the tests that were run.

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



if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMessageManager)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)