"""
Unit tests for the ChatServer class using the unittest framework.

This file contains a suite of tests that validate the functionality of the ChatServer,
which handles operations such as user login, message sending/receiving, account deletion,
and listing accounts. It simulates various scenarios including:
  - Creating a new account and logging in.
  - Logging into an existing account with correct or incorrect credentials.
  - Retrieving pending messages.
  - Sending messages to online and offline users.
  - Receiving messages via a streaming interface.
  - Deleting an account with pending messages (with or without confirmation).
  - Listing registered accounts.

The tests use mock patches to simulate interactions with external functions such as loading
and saving accounts and messages. The fake contexts simulate the behavior of a gRPC call context.
"""

import sys

sys.path.append("../")  # Adjust system path to import modules from the parent directory
import unittest
from unittest.mock import patch, MagicMock
import queue  # Used to simulate message queues for active clients
import re  # Imported for regular expression support, though not explicitly used here

# Importing the generated protobuf and gRPC modules.
import chatapp_pb2
import chatapp_pb2_grpc

# Importing the ChatServer class and related global variables from the server module.
from server import (
    ChatServer,
    active_clients,
    pending_messages,
    FILE_PATH,
    PENDING_MESSAGES_FILE_PATH,
)

# these will need to be completely new with the new wire protocol


class FakeContext:
    """
    A simple fake context class to simulate gRPC request contexts in tests.

    This stub implementation of the context provides the is_active() method,
    which always returns False. It is used in tests to simulate the gRPC context
    passed to server methods without requiring an actual gRPC environment.
    """

    def is_active(self):
        # Always return False to simulate an inactive context
        return False


class TestChatServer(unittest.TestCase):
    """
    Test suite for verifying the behavior of the ChatServer class.

    This class includes tests that cover various aspects of the ChatServer, such as:
      - New account creation and login.
      - Existing account login success and failure.
      - Retrieving pending messages.
      - Sending messages when recipients are online or offline.
      - Receiving streamed messages.
      - Account deletion with and without pending messages confirmation.
      - Listing of all accounts.
    """

    def setUp(self):
        """
        Set up the test environment before each test.

        This method clears the global dictionaries for active clients and pending messages,
        ensuring that each test starts with a clean slate. It then instantiates a new ChatServer.
        """
        active_clients.clear()  # Reset active clients for a fresh test environment
        pending_messages.clear()  # Reset pending messages to avoid interference between tests
        self.server = ChatServer()  # Instantiate the ChatServer to be tested

    @patch("server.load_accounts")
    @patch("server.create_account")
    def test_Login_new_account(self, mock_create_account, mock_load_accounts):
        """
        Test the Login method for creating a new account.

        This test simulates a login request with the 'is_new' flag set to True, meaning the
        user wants to create a new account. It verifies that:
          - The accounts database is initially empty.
          - The server responds with a success message after account creation.
          - The create_account function is invoked with the correct parameters.
        """
        # Simulate an empty accounts database.
        mock_load_accounts.return_value = {}
        # Create a LoginRequest for a new user.
        request = chatapp_pb2.LoginRequest(
            username="newuser", password="hashedpass", is_new=True
        )
        fake_context = FakeContext()  # Use a fake context for testing
        response = self.server.Login(request, fake_context)
        # Assert that the response indicates a successful account creation and login.
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Account created! You are now logged in.")
        # Verify that create_account was called with the correct arguments.
        mock_create_account.assert_called_once_with("newuser", "hashedpass", FILE_PATH)

    @patch("server.load_accounts")
    def test_Login_existing_account_success(self, mock_load_accounts):
        """
        Test the Login method for an existing account with correct credentials.

        This test simulates a login request for an existing user whose password matches the stored password.
        It checks that the response indicates successful login.
        """
        # Simulate an existing account with matching credentials.
        mock_load_accounts.return_value = {"existinguser": {"password": "hashedpass"}}
        # Create a LoginRequest for the existing user.
        request = chatapp_pb2.LoginRequest(
            username="existinguser", password="hashedpass", is_new=False
        )
        fake_context = FakeContext()  # Use a fake context for the RPC call
        response = self.server.Login(request, fake_context)
        # Assert that the login was successful.
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Success! You are now logged in.")

    @patch("server.load_accounts")
    def test_Login_existing_account_failure(self, mock_load_accounts):
        """
        Test the Login method for an existing account with incorrect credentials.

        This test simulates a login request where the provided password does not match the stored password.
        It ensures that the server responds with an appropriate failure message.
        """
        # Simulate an existing account with a different stored password.
        mock_load_accounts.return_value = {"existinguser": {"password": "otherpass"}}
        # Create a LoginRequest with an incorrect password.
        request = chatapp_pb2.LoginRequest(
            username="existinguser", password="hashedpass", is_new=False
        )
        fake_context = FakeContext()  # Use a fake context for testing
        response = self.server.Login(request, fake_context)
        # Assert that the login failed and the error message is correct.
        self.assertFalse(response.success)
        self.assertEqual(
            response.message, "This username/password is not registered with us!"
        )

    @patch("server.load_pending_messages")
    @patch("server.delete_pending_messages")
    def test_GetPendingMessages(self, mock_delete_pending, mock_load_pending):
        """
        Test retrieving pending messages for a user.

        This test simulates the presence of pending messages for a specific user. It verifies that:
          - The aggregated message string in the response contains the expected content.
          - The list of messages returned has the correct number of messages.
          - The delete_pending_messages function is called to clear the messages after retrieval.
        """
        # Simulate pending messages for user "tester".
        fake_pending = {"tester": [("user1", "Hello"), ("user2", "Hi")]}
        mock_load_pending.return_value = fake_pending
        # Create a PendingMessagesRequest for user "tester".
        request = chatapp_pb2.PendingMessagesRequest(username="tester")
        fake_context = FakeContext()  # Use a fake context for the RPC call
        response = self.server.GetPendingMessages(request, fake_context)
        # Verify that the response message contains the pending messages.
        self.assertIn("user1: Hello", response.message)
        self.assertIn("user2: Hi", response.message)
        # Verify that the number of messages is as expected.
        self.assertEqual(len(response.messages), 2)
        # Confirm that delete_pending_messages was called with the correct parameters.
        mock_delete_pending.assert_called_once_with(
            PENDING_MESSAGES_FILE_PATH, "tester", 10
        )

    @patch("server.delete_pending_messages")
    def test_MoreMessages(self, mock_delete_pending):
        """
        Test retrieving additional messages for a user.

        This test prepopulates the global pending_messages dictionary with several messages for a user,
        then verifies that the MoreMessages method returns all of them and that the deletion of messages is performed.
        """
        # Prepopulate pending_messages for user "tester".
        pending_messages["tester"] = [
            ("user1", "Message1"),
            ("user2", "Message2"),
            ("user3", "Message3"),
        ]
        # Create a MoreMessagesRequest for user "tester".
        request = chatapp_pb2.MoreMessagesRequest(username="tester")
        fake_context = FakeContext()  # Use a fake context for testing
        response = self.server.MoreMessages(request, fake_context)
        # Check that all messages are returned.
        self.assertEqual(len(response.messages), 3)
        self.assertEqual(response.message, "More messages retrieved.\n")
        # Ensure the delete_pending_messages function was called to clear the messages.
        mock_delete_pending.assert_called_once_with(
            PENDING_MESSAGES_FILE_PATH, "tester", 10
        )

    def test_SendMessage_online(self):
        """
        Test sending a message when the recipient is online.

        This test simulates an online recipient by adding a queue to the active_clients dictionary.
        It verifies that:
          - The message is delivered immediately via the recipient's queue.
          - The response indicates that the message was delivered.
        """
        # Simulate an online recipient "receiver" by creating a message queue.
        q = queue.Queue()
        active_clients["receiver"] = q  # Register the recipient as active
        # Create a SendMessageRequest with sender, recipient, and message details.
        request = chatapp_pb2.SendMessageRequest(
            sender="sender", recipient="receiver", message="Hello"
        )
        fake_context = FakeContext()  # Use a fake context for testing
        response = self.server.SendMessage(request, fake_context)
        # Assert that the message was delivered and the response is correct.
        self.assertTrue(response.delivered)
        self.assertEqual(response.message, "Message delivered.")
        # Verify that the message is in the recipient's queue.
        self.assertEqual(q.get(), ("sender", "Hello"))

    @patch("server.save_pending_messages")
    def test_SendMessage_offline(self, mock_save_pending):
        """
        Test sending a message when the recipient is offline.

        This test verifies that if the recipient is not active, the server saves the message as pending.
        It checks that:
          - The response indicates the recipient is offline.
          - The pending_messages structure is updated with the new message.
          - The save_pending_messages function is invoked.
        """
        # Simulate sending a message to an offline recipient "receiver".
        request = chatapp_pb2.SendMessageRequest(
            sender="sender", recipient="receiver", message="Hello"
        )
        fake_context = FakeContext()  # Use a fake context for the RPC call
        response = self.server.SendMessage(request, fake_context)
        # Assert that the message is not delivered immediately.
        self.assertFalse(response.delivered)
        self.assertEqual(
            response.message, "Recipient offline. Message saved as pending."
        )
        # Confirm that pending_messages now contains the message for the recipient.
        self.assertIn("receiver", pending_messages)
        self.assertIn(("sender", "Hello"), pending_messages["receiver"])
        # Verify that the save_pending_messages function was called.
        mock_save_pending.assert_called_once()

    def test_ReceiveMessages(self):
        """
        Test receiving a stream of messages.

        This test simulates a user's message queue containing a message and verifies that the ReceiveMessages
        method streams the message correctly until the queue is empty.
        """
        # Create a message queue and add a message for user "tester".
        q = queue.Queue()
        q.put(("user1", "Stream message"))
        active_clients["tester"] = q  # Register the user as active with a message queue
        # Create a ReceiveMessagesRequest for user "tester".
        request = chatapp_pb2.ReceiveMessagesRequest(username="tester")

        # Define a fake stream context that returns active as long as the queue is not empty.
        class FakeStreamContext:
            """
            A fake streaming context to simulate an active message stream.

            The is_active() method returns True until the message queue is empty.
            """

            def is_active(self):
                return not q.empty()

        fake_context = FakeStreamContext()  # Instantiate the fake stream context
        generator = self.server.ReceiveMessages(request, fake_context)
        messages = list(generator)  # Collect messages from the streaming generator
        # Assert that one message is received with the correct sender and content.
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].sender, "user1")
        self.assertEqual(messages[0].message, "Stream message")

    @patch("server.load_pending_messages")
    @patch("server.delete_pending_messages")
    @patch("server.delete_account")
    def test_DeleteAccount_pending_no_confirm(
        self, mock_delete_account, mock_delete_pending, mock_load_pending
    ):
        """
        Test account deletion when pending messages exist and deletion is not confirmed.

        This test simulates an account deletion request for a user who has pending messages.
        With the 'confirm' flag set to False, the deletion should not proceed, and the server
        should instruct the user to confirm deletion.
        """
        # Simulate pending messages for user "tester".
        mock_load_pending.return_value = {"tester": [("user1", "Hello")]}
        # Create a DeleteAccountRequest with confirmation disabled.
        request = chatapp_pb2.DeleteAccountRequest(username="tester", confirm=False)
        fake_context = FakeContext()  # Use a fake context for the RPC call
        response = self.server.DeleteAccount(request, fake_context)
        # Verify that the deletion did not occur and the appropriate message is returned.
        self.assertFalse(response.success)
        self.assertEqual(
            response.message, "You have unread messages. Confirm deletion to proceed."
        )
        # Ensure that delete_account was not called since confirmation was not given.
        mock_delete_account.assert_not_called()

    @patch("server.load_pending_messages")
    @patch("server.delete_pending_messages")
    @patch("server.delete_account")
    def test_DeleteAccount_pending_confirm(
        self, mock_delete_account, mock_delete_pending, mock_load_pending
    ):
        """
        Test account deletion when pending messages exist and deletion is confirmed.

        This test simulates an account deletion request for a user with pending messages where the
        'confirm' flag is set to True. It verifies that the account is deleted, pending messages are cleared,
        and a success message is returned.
        """
        # Simulate multiple pending messages for user "tester".
        mock_load_pending.return_value = {
            "tester": [("user1", "Hello"), ("user2", "Hi")]
        }
        # Create a DeleteAccountRequest with confirmation enabled.
        request = chatapp_pb2.DeleteAccountRequest(username="tester", confirm=True)
        fake_context = FakeContext()  # Use a fake context for testing
        response = self.server.DeleteAccount(request, fake_context)
        # Assert that the deletion was successful.
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Account deletion successful.")
        # Verify that delete_account is called with the correct username and file path.
        mock_delete_account.assert_called_once_with("tester", FILE_PATH)
        # Verify that pending messages are deleted with the correct parameters.
        mock_delete_pending.assert_called_once_with(
            PENDING_MESSAGES_FILE_PATH, "tester", 2
        )

    @patch("server.list_accounts")
    def test_ListAccounts(self, mock_list_accounts):
        """
        Test the ListAccounts method for listing all accounts.

        This test simulates a request to list accounts, ensuring that the server returns the correct
        list of account names along with a success message.
        """
        # Simulate list_accounts returning a newline-separated string of usernames.
        mock_list_accounts.return_value = "user1\nuser2\nuser3\n"
        # Create a ListAccountsRequest with a filter value.
        request = chatapp_pb2.ListAccountsRequest(filter="all")
        fake_context = FakeContext()  # Use a fake context for testing
        response = self.server.ListAccounts(request, fake_context)
        # Verify that the returned list of accounts matches the expected result.
        self.assertEqual(response.accounts, ["user1", "user2", "user3"])
        self.assertEqual(response.message, "Accounts listed successfully.")
        # Confirm that list_accounts was called with the proper file path.
        mock_list_accounts.assert_called_once_with(FILE_PATH)


class CustomTestRunner(unittest.TextTestRunner):
    """
    Custom test runner with enhanced verbosity and summary output.

    This runner extends unittest.TextTestRunner to provide a summary of test results,
    including the total number of tests run, and counts of failures or errors.
    """

    def run(self, test):
        """
        Run the provided test suite and output a summary of results.

        Args:
            test: The test suite to run.

        Returns:
            The test result after executing the suite.
        """
        result = super().run(test)  # Run tests using the base class's implementation
        print("\nTest Summary")
        print("------------")
        print(f"{result.testsRun} tests run.")
        if not result.wasSuccessful():
            print(f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
        else:
            print("All tests passed!")
        return result


if __name__ == "__main__":
    # Load all tests from the TestChatServer test case.
    suite = unittest.TestLoader().loadTestsFromTestCase(TestChatServer)
    # Create a custom test runner instance with increased verbosity.
    runner = CustomTestRunner(verbosity=2)
    # Run the test suite.
    runner.run(suite)
