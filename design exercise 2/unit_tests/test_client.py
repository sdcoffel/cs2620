import unittest
from unittest.mock import patch, Mock, MagicMock
import json
import socket
import sys

#these will need to be fixed w new wire protocol
sys.path.append("../")
from client import Client
from settings import JSON_MODE


class TestChatClient(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.client = Client()
        # Create a mock socket
        self.mock_socket = Mock(spec=socket.socket)
        self.client.client_socket = self.mock_socket

    def tearDown(self):
        """Clean up after each test method."""
        self.client.close_connection()

    def test_init(self):
        """Test client initialization."""
        client = Client()
        self.assertIsNone(client.username)
        self.assertFalse(client.connected)
        self.assertIsInstance(client.client_socket, socket.socket)

    def test_hash_password(self):
        """Test password hashing."""
        password = "testpass123"
        hashed = self.client.hash_password(password)
        # Test that same password produces same hash
        self.assertEqual(hashed, self.client.hash_password(password))
        # Test hashed password and password are different
        self.assertNotEqual(hashed, password)
        # Test hash is correct length for SHA256
        self.assertEqual(len(hashed), 64)

    @patch("socket.socket")
    def test_start_client(self, mock_socket_class):
        """Test client connection to server."""
        # Create a new mock socket instance
        mock_socket_instance = Mock()
        # Set up the mock socket class to return our mock instance
        mock_socket_class.return_value = mock_socket_instance

        # Create a new client (don't use self.client as it already has a mock socket)
        client = Client()

        host = "localhost"
        port = 12345
        client.start_client(host, port)

        # Now verify the connect was called
        mock_socket_instance.connect.assert_called_once_with((host, port))
        self.assertTrue(client.connected)

    def test_handle_login_new_account(self):
        """Test handling login for new account creation."""
        username = "newuser"
        password = "password123"
        existing = "no"

        # Mock server response for successful account creation
        expected_response = "Account created! You are now logged in."
        if JSON_MODE:
            self.mock_socket.recv.return_value = json.dumps(
                {"data": expected_response}
            ).encode("utf-8")
        else:
            self.mock_socket.recv.return_value = expected_response.encode("utf-8")

        response = self.client.handle_login(username, password, existing)

        # Verify the client sent correct login data
        if JSON_MODE:
            expected_send_data = {
                "username": username,
                "password": self.client.hash_password(password),
                "existing": existing,
            }
            self.mock_socket.send.assert_called_once_with(
                json.dumps(expected_send_data).encode("utf-8")
            )
        else:
            expected_credentials = (
                f"{username},{self.client.hash_password(password)},{existing}"
            )
            self.mock_socket.send.assert_called_once_with(
                expected_credentials.encode("utf-8")
            )

        # Check username was set
        self.assertEqual(self.client.username, username)

    def test_send_messages(self):
        """Test sending messages to a recipient."""
        recipient = "testuser"
        message = "Hello, test user!"

        self.client.send_messages(recipient, message)

        expected_message = f"{recipient}:{message}"
        if JSON_MODE:
            self.mock_socket.send.assert_called_once_with(
                json.dumps({"raw_message": expected_message}).encode("utf-8")
            )
        else:
            self.mock_socket.send.assert_called_once_with(
                expected_message.encode("utf-8")
            )

    def test_receive_messages_json_mode(self):
        """Test receiving messages in JSON mode."""
        if not JSON_MODE:
            self.skipTest("Test only applicable in JSON mode")

        test_message = {"sender": "testuser", "message": "Test message"}
        self.mock_socket.recv.return_value = json.dumps(test_message).encode("utf-8")

        received = self.client.receive_messages()
        self.assertEqual(received, json.dumps(test_message))

    def test_receive_messages_plain_mode(self):
        """Test receiving messages in plain text mode."""
        if JSON_MODE:
            self.skipTest("Test only applicable in plain text mode")

        test_message = "testuser: Test message"
        self.mock_socket.recv.return_value = test_message.encode("utf-8")

        received = self.client.receive_messages()
        self.assertEqual(received, test_message)

    def test_delete_message(self):
        """Test message deletion request."""
        message = "Test message to delete"
        server_response = "Message deleted successfully"

        if JSON_MODE:
            self.mock_socket.recv.return_value = json.dumps(
                {"data": server_response}
            ).encode("utf-8")
        else:
            self.mock_socket.recv.return_value = server_response.encode("utf-8")

        self.client.delete_message(message)

        if JSON_MODE:
            expected_send = json.dumps({"raw_message": "delete " + message}).encode(
                "utf-8"
            )
        else:
            expected_send = ("delete" + message).encode("utf-8")

        self.mock_socket.send.assert_called_once_with(expected_send)

    def test_list_accounts(self):
        """Test requesting account list."""
        test_accounts = ["user1", "user2", "user3"]

        if JSON_MODE:
            self.mock_socket.recv.return_value = json.dumps(
                {"data": test_accounts}
            ).encode("utf-8")
        else:
            self.mock_socket.recv.return_value = "\n".join(test_accounts).encode(
                "utf-8"
            )

        accounts = self.client.list_accounts()

        if JSON_MODE:
            self.mock_socket.send.assert_called_once_with(
                json.dumps({"raw_message": "list_accounts"}).encode("utf-8")
            )
        else:
            self.mock_socket.send.assert_called_once_with(
                "list_accounts".encode("utf-8")
            )

        self.assertEqual(len(accounts), len(test_accounts))

    def test_wildcard_filtering(self):
        """Test wildcard pattern matching for account filtering."""
        test_accounts = ["user1", "user2", "admin1", "admin2"]

        # Test "all" pattern
        filtered = self.client.wildcard("all", test_accounts)
        self.assertEqual(filtered, test_accounts)

        # Test specific pattern
        filtered = self.client.wildcard("admin.*", test_accounts)
        self.assertEqual(filtered, ["admin1", "admin2"])

        # Test no matches
        filtered = self.client.wildcard("nonexistent.*", test_accounts)
        self.assertEqual(filtered, "No accounts match the given pattern.")





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


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestChatClient)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)