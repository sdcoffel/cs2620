import unittest
from unittest.mock import patch, Mock, MagicMock, call
import json
import socket
import threading
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import JSON_MODE

# Define globals that we'll use in tests
test_active_clients = {}
test_messages = {}
test_pending_messages = {}


class TestServer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset test globals
        test_active_clients.clear()
        test_messages.clear()
        test_pending_messages.clear()

        # Create mock socket and connection
        self.mock_socket = Mock(spec=socket.socket)
        self.mock_connection = Mock(spec=socket.socket)
        self.mock_address = ("127.0.0.1", 12345)

        # Import server module in setUp to avoid circular imports
        import server

        self.server = server

        # Patch the global variables in server
        self.patcher1 = patch.dict("server.active_clients", test_active_clients)
        self.patcher2 = patch.dict("server.messages", test_messages)
        self.patcher3 = patch.dict("server.pending_messages", test_pending_messages)

        # Start the patches
        self.patcher1.start()
        self.patcher2.start()
        self.patcher3.start()

    def tearDown(self):
        """Clean up after each test."""
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()

    @patch("server.save_messages")
    def test_send_message_to_active_client(self, mock_save_messages):
        """Test sending a message to an active client."""
        # Setup
        sender = "user1"
        recipient = "user2"
        message = "Hello, user2!"
        recipient_socket = Mock(spec=socket.socket)

        # Add recipient to active clients
        test_active_clients[recipient] = {"socket": recipient_socket}

        # Send message
        self.server.send_message(recipient, sender, message)

        # Verify message was saved
        mock_save_messages.assert_called_once()

        # Verify message was sent to recipient
        if JSON_MODE:
            expected_data = {"sender": sender, "message": message}
            recipient_socket.send.assert_called_once_with(
                json.dumps(expected_data).encode("utf-8")
            )
        else:
            expected_message = f"{sender}: {message}".encode("utf-8")
            recipient_socket.send.assert_called_once_with(expected_message)

    @patch("server.save_messages")
    @patch("server.save_pending_messages")
    def test_send_message_to_offline_client(
        self, mock_save_pending, mock_save_messages
    ):
        """Test sending a message to an offline client."""
        sender = "user1"
        recipient = "offline_user"
        message = "Hello, are you there?"

        # Send message to offline user
        self.server.send_message(recipient, sender, message)

        # Verify message was saved to pending messages
        self.assertIn(recipient, test_pending_messages)
        self.assertEqual(test_pending_messages[recipient][-1], (sender, message))
        mock_save_pending.assert_called_once()
        mock_save_messages.assert_called_once()

    @patch("server.load_accounts")
    @patch("server.create_account")
    def test_client_handler_login_new_account(
        self, mock_create_account, mock_load_accounts
    ):
        """Test client handler creating new account."""
        mock_load_accounts.return_value = {}

        # Setup mock connection
        if JSON_MODE:
            login_data = {
                "username": "newuser",
                "password": "hashedpassword",
                "existing": "no",
            }
            self.mock_connection.recv.return_value = json.dumps(login_data).encode(
                "utf-8"
            )
        else:
            credentials = "newuser,hashedpassword,no"
            self.mock_connection.recv.return_value = credentials.encode("utf-8")

        # Mock a second recv call to simulate client disconnection
        self.mock_connection.recv.side_effect = [
            self.mock_connection.recv.return_value,
            "",
        ]

        # Start client handler
        self.server.client_handler(self.mock_connection, self.mock_address)

        # Verify response was sent
        if JSON_MODE:
            expected_response = {"data": "Account created! You are now logged in."}
            self.mock_connection.send.assert_any_call(
                json.dumps(expected_response).encode("utf-8")
            )
        else:
            expected_response = "Account created! You are now logged in.\n"
            self.mock_connection.send.assert_any_call(expected_response.encode("utf-8"))

    @patch("socket.socket")
    @patch("server.load_pending_messages")
    def test_start_server(self, mock_load_pending, mock_socket):
        """Test server startup."""
        # Setup mock socket
        mock_server_socket = Mock()
        mock_socket.return_value = mock_server_socket

        # Make accept() raise an exception to stop the server loop
        mock_server_socket.accept.side_effect = Exception("Test shutdown")

        # Start server
        with self.assertRaises(Exception):
            self.server.start_server()

        # Verify server socket was created and configured correctly
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_server_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )
        mock_server_socket.bind.assert_called_once_with(("localhost", 12345))
        mock_server_socket.listen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
