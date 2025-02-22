import unittest
from unittest.mock import patch, MagicMock
import sys
import re
import grpc

# Ensure the client module is in the path.
sys.path.append("../")
from client import Client
import chatapp_pb2   
import chatapp_pb2_grpc

class TestChatClient(unittest.TestCase):
    def setUp(self):
        """Set up a fresh Client instance before each test and replace the stub with a MagicMock."""
        self.client = Client()
        # We'll simulate the stub (and thus server responses) via a MagicMock.
        self.client.stub = MagicMock()
        # For tests that depend on a logged-in user, set a default username.
        self.client.username = "tester"


    def tearDown(self):
        """Close the client channel (if set) after each test."""
        if self.client.channel:
            self.client.channel.close()


    def test_init(self):
        """Test that a new Client instance is initialized with no channel, stub, or username."""
        client = Client()
        self.assertIsNone(client.username)
        self.assertIsNone(client.channel)
        self.assertIsNone(client.stub)


    def test_hash_password(self):
        """Test that the hash_password function produces consistent, correctly formatted SHA256 hashes."""
        password = "testpassword"
        hashed1 = self.client.hash_password(password)
        hashed2 = self.client.hash_password(password)
        self.assertEqual(hashed1, hashed2)
        self.assertNotEqual(hashed1, password)
        self.assertEqual(len(hashed1), 64)


    @patch("grpc.insecure_channel")
    @patch("chatapp_pb2_grpc.ChatServiceStub")
    def test_start_client(self, mock_stub_class, mock_insecure_channel):
        """Test that start_client properly initializes the gRPC channel and stub."""
        fake_channel = MagicMock()
        mock_insecure_channel.return_value = fake_channel
        fake_stub = MagicMock()
        mock_stub_class.return_value = fake_stub

        client = Client()
        client.start_client("localhost", 50051)
        mock_insecure_channel.assert_called_once_with("localhost:50051")
        mock_stub_class.assert_called_once_with(fake_channel)
        self.assertIsNotNone(client.channel)
        self.assertIsNotNone(client.stub)


    def test_handle_login_new_account(self):
        """Test handling login for new account creation via gRPC."""
        username = "newuser"
        password = "password123"
        existing = "no"  # means the account does not exist
        hashed_password = self.client.hash_password(password)
        fake_response = chatapp_pb2.LoginResponse(success=True, message="Account created! You are now logged in.")
        self.client.stub.Login.return_value = fake_response

        success, message = self.client.handle_login(username, password, existing)
        self.assertTrue(success)
        self.assertEqual(message, "Account created! You are now logged in.")
        self.assertEqual(self.client.username, username)
        self.client.stub.Login.assert_called_once()
        request_arg = self.client.stub.Login.call_args[0][0]
        self.assertEqual(request_arg.username, username)
        self.assertEqual(request_arg.password, hashed_password)
        self.assertTrue(request_arg.is_new)


    def test_get_pending_messages(self):
        """Test retrieving pending messages via gRPC."""
        # Create fake pending messages response.
        fake_msg1 = chatapp_pb2.PendingMessage(sender="user1", message="Hello")
        fake_msg2 = chatapp_pb2.PendingMessage(sender="user2", message="Hi there")
        fake_response = chatapp_pb2.PendingMessagesResponse(
            messages=[fake_msg1, fake_msg2],
            message="You have pending messages"
        )
        self.client.stub.GetPendingMessages.return_value = fake_response

        result = self.client.get_pending_messages()
        self.assertIn("user1: Hello", result)
        self.assertIn("user2: Hi there", result)
        self.client.stub.GetPendingMessages.assert_called_once()


    def test_grab_more_messages(self):
        """Test grabbing more messages via gRPC."""
        fake_response = chatapp_pb2.MoreMessagesResponse(
            messages=[],
            message="No more messages."
        )
        self.client.stub.MoreMessages.return_value = fake_response

        result = self.client.grab_more_messages()
        self.assertEqual(result, "No more messages.")
        self.client.stub.MoreMessages.assert_called_once()


    def test_set_recipient(self):
        """Test that set_recipient correctly stores the default recipient."""
        self.client.set_recipient("target_user")
        self.assertEqual(self.client.recipient, "target_user")


    def test_receive_messages(self):
        """Test that ReceiveMessages correctly yields messages from a streaming RPC."""
        # Define a fake generator to simulate a streaming response.
        def fake_generator():
            yield chatapp_pb2.ChatMessageResponse(sender="user1", message="Test message 1")
            yield chatapp_pb2.ChatMessageResponse(sender="user2", message="Test message 2")
        self.client.stub.ReceiveMessages.return_value = fake_generator()

        messages = list(self.client.ReceiveMessages())
        self.assertEqual(len(messages), 2)
        self.assertIn("user1: Test message 1", messages[0])
        self.assertIn("user2: Test message 2", messages[1])
        self.client.stub.ReceiveMessages.assert_called_once()


    def test_send_messages(self):
        """Test sending a message via gRPC."""

        #initialize recipient and message
        recipient = "target_user"
        message = "Hello there!"
        self.client.set_recipient(recipient)

        #simulate a response on the stub 
        fake_response = chatapp_pb2.SendMessageResponse(delivered=True, message="Message delivered.")
        self.client.stub.SendMessage.return_value = fake_response

        #simulate deliverance
        delivered = self.client.send_messages(recipient, message)
        self.assertTrue(delivered)
        self.client.stub.SendMessage.assert_called_once()
        request_arg = self.client.stub.SendMessage.call_args[0][0]

        #assertions to pass
        self.assertEqual(request_arg.sender, self.client.username)
        self.assertEqual(request_arg.recipient, recipient)
        self.assertEqual(request_arg.message, message)


    def test_delete_account(self):
        """Test account deletion via gRPC."""
        fake_response = chatapp_pb2.DeleteAccountResponse(success=True, message="Account deleted successfully.")
        self.client.stub.DeleteAccount.return_value = fake_response

        response = self.client.delete_account()
        self.assertEqual(response, "Account deleted successfully.")
        self.client.stub.DeleteAccount.assert_called_once()


    def test_list_accounts(self):
        """Test listing accounts via gRPC."""
        test_accounts = ["user1", "user2", "user3"]
        fake_response = chatapp_pb2.ListAccountsResponse(
            accounts=test_accounts,
            message="Accounts listed successfully."
        )
        self.client.stub.ListAccounts.return_value = fake_response

        accounts = self.client.list_accounts("all")
        self.assertEqual(accounts, test_accounts)
        self.client.stub.ListAccounts.assert_called_once()


class CustomTestRunner(unittest.TextTestRunner):
    """Custom test runner with additional summary output."""
    def run(self, test):
        result = super().run(test)
        print("\nTest Summary")
        print("------------")
        print(f"{result.testsRun} tests run.")
        if not result.wasSuccessful():
            print(f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
        else:
            print("All tests passed!")
        return result


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestChatClient)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)
