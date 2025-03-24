import pytest
import sys
import os
import grpc
import uuid
import multiprocessing
from unittest.mock import MagicMock, patch, mock_open

# Import modules to test
import client
import chatapp_pb2
import chatapp_pb2_grpc

# Import server module with proper mocking
import importlib

# =========================================================================
# Tests for client.py
# =========================================================================
class TestClient:
    @pytest.fixture
    def mock_stub(self):
        """Create a mock gRPC stub for testing."""
        return MagicMock()
    
    @pytest.fixture
    def client_instance(self, mock_stub):
        """Create a client instance with mocked stub."""
        client_obj = client.Client("localhost", 50051)
        client_obj.stub = mock_stub
        client_obj.username = "testuser"
        return client_obj

    def test_hash_password(self):
        """Test password hashing functionality."""
        result = client.Client.hash_password("password123")
        # SHA-256 hash of "password123"
        expected = "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f"
        assert result == expected

    def test_handle_login_new_account_success(self, client_instance, mock_stub):
        """Test login handling for new account creation."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.message = "Account created successfully"
        mock_stub.Login.return_value = mock_response
        
        # Test login with "no" indicating new account
        success, message = client_instance.handle_login("newuser", "password123", "no")
        
        # Verify stub was called with correct request
        mock_stub.Login.assert_called_once()
        request = mock_stub.Login.call_args[0][0]
        assert request.username == "newuser"
        assert request.is_new is True
        
        # Check return values
        assert success is True
        assert message == "Account created successfully"
        assert client_instance.username == "newuser"

    def test_handle_login_existing_account_failure(self, client_instance, mock_stub):
        """Test login handling for existing account with incorrect credentials."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.message = "Invalid credentials"
        mock_stub.Login.return_value = mock_response
        
        # Test login with "yes" indicating existing account
        success, message = client_instance.handle_login("existinguser", "wrongpassword", "yes")
        
        # Verify stub was called with correct request
        mock_stub.Login.assert_called_once()
        request = mock_stub.Login.call_args[0][0]
        assert request.username == "existinguser"
        assert request.is_new is False
        
        # Check return values
        assert success is False
        assert message == "Invalid credentials"
        assert client_instance.username != "existinguser"  # Username shouldn't be set on failed login

    def test_get_pending_messages_with_messages(self, client_instance, mock_stub):
        """Test retrieving pending messages when messages exist."""
        # Create mock messages
        mock_message1 = MagicMock()
        mock_message1.sender = "sender1"
        mock_message1.message = "Hello"
        
        mock_message2 = MagicMock()
        mock_message2.sender = "sender2"
        mock_message2.message = "How are you?"
        
        # Configure mock response with messages
        mock_response = MagicMock()
        mock_response.messages = [mock_message1, mock_message2]
        mock_response.message = "You have 2 pending messages"
        mock_stub.GetPendingMessages.return_value = mock_response
        
        # Call method
        result = client_instance.get_pending_messages()
        
        # Verify stub was called with correct request
        mock_stub.GetPendingMessages.assert_called_once()
        request = mock_stub.GetPendingMessages.call_args[0][0]
        assert request.username == "testuser"
        
        # Verify result contains messages
        assert "sender1: Hello" in result
        assert "sender2: How are you?" in result

    def test_get_pending_messages_no_messages(self, client_instance, mock_stub):
        """Test retrieving pending messages when no messages exist."""
        # Configure mock response with no messages
        mock_response = MagicMock()
        mock_response.messages = []
        mock_response.message = "You have 0 pending messages."
        mock_stub.GetPendingMessages.return_value = mock_response
        
        # Call method
        result = client_instance.get_pending_messages()
        
        # Verify stub was called with correct request
        mock_stub.GetPendingMessages.assert_called_once()
        request = mock_stub.GetPendingMessages.call_args[0][0]
        assert request.username == "testuser"
        
        # Verify result shows no messages
        assert "You have 0 pending messages." in result

    def test_grab_more_messages(self, client_instance, mock_stub):
        """Test retrieving more messages."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.message = "More messages retrieved"
        mock_stub.MoreMessages.return_value = mock_response
        
        # Call method
        result = client_instance.grab_more_messages()
        
        # Verify stub was called with correct request
        mock_stub.MoreMessages.assert_called_once()
        request = mock_stub.MoreMessages.call_args[0][0]
        assert request.username == "testuser"
        
        # Verify result
        assert result == "More messages retrieved"

    def test_set_recipient(self, client_instance):
        """Test setting the default recipient."""
        client_instance.set_recipient("recipient1")
        assert client_instance.recipient == "recipient1"

    def test_receive_messages(self, client_instance, mock_stub):
        """Test receiving messages stream."""
        # Create mock messages for the stream
        mock_message1 = MagicMock()
        mock_message1.sender = "sender1"
        mock_message1.message = "Hello"
        
        mock_message2 = MagicMock()
        mock_message2.sender = "sender2"
        mock_message2.message = "How are you?"
        
        # Configure mock stream
        mock_stub.ReceiveMessages.return_value = [mock_message1, mock_message2]
        
        # Call method and collect results
        results = list(client_instance.ReceiveMessages())
        
        # Verify stub was called with correct request
        mock_stub.ReceiveMessages.assert_called_once()
        request = mock_stub.ReceiveMessages.call_args[0][0]
        assert request.username == "testuser"
        
        # Verify results
        assert "Received from sender1: Hello" in results
        assert "Received from sender2: How are you?" in results

    def test_send_messages(self, client_instance, mock_stub):
        """Test sending messages."""
        # Set recipient
        client_instance.recipient = "recipient1"
        
        # Configure mock response
        mock_response = MagicMock()
        mock_response.delivered = True
        mock_response.message = "Message sent"
        mock_stub.SendMessage.return_value = mock_response
        
        # Call method
        result = client_instance.send_messages("recipient1", "Hello there")
        
        # Verify stub was called with correct request
        mock_stub.SendMessage.assert_called_once()
        request = mock_stub.SendMessage.call_args[0][0]
        assert request.sender == "testuser"
        assert request.recipient == "recipient1"
        assert request.message == "Hello there"
        
        # Verify result
        assert result is True

    def test_send_messages_no_recipient(self, client_instance, mock_stub):
        """Test sending messages with no recipient set."""
        # Ensure recipient is not set
        if hasattr(client_instance, "recipient"):
            delattr(client_instance, "recipient")
        
        # Call method
        result = client_instance.send_messages("", "Hello there")
        
        # Verify stub was not called
        mock_stub.SendMessage.assert_not_called()
        
        # Verify result
        assert result is False

    def test_delete_account(self, client_instance, mock_stub):
        """Test account deletion."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.message = "Account deleted successfully"
        mock_stub.DeleteAccount.return_value = mock_response
        
        # Call method
        result = client_instance.delete_account()
        
        # Verify stub was called with correct request
        mock_stub.DeleteAccount.assert_called_once()
        request = mock_stub.DeleteAccount.call_args[0][0]
        assert request.username == "testuser"
        assert request.confirm is True
        
        # Verify result
        assert result == "Account deleted successfully"

    def test_list_accounts(self, client_instance, mock_stub):
        """Test listing accounts."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.accounts = ["user1", "user2", "user3"]
        mock_response.message = "Accounts listed successfully"
        mock_stub.ListAccounts.return_value = mock_response
        
        # Call method with default filter
        result = client_instance.list_accounts()
        
        # Verify stub was called with correct request
        mock_stub.ListAccounts.assert_called_once()
        request = mock_stub.ListAccounts.call_args[0][0]
        assert request.filter == "all"
        
        # Verify result
        assert result == ["user1", "user2", "user3"]
        
        # Reset mock for next test
        mock_stub.ListAccounts.reset_mock()
        
        # Test with custom filter
        result = client_instance.list_accounts("user*")
        
        # Verify stub was called with correct request
        mock_stub.ListAccounts.assert_called_once()
        request = mock_stub.ListAccounts.call_args[0][0]
        assert request.filter == "user*"

    @patch('grpc.insecure_channel')
    def test_start_client_success(self, mock_channel):
        """Test successful client startup."""
        # Configure mock
        mock_stub = MagicMock()
        mock_channel.return_value = mock_stub
        
        # Create client and start it
        client_obj = client.Client("localhost", 50051)
        client_obj.start_client("localhost", 50051)
        
        # Verify channel was created with correct address
        mock_channel.assert_called_once_with('localhost:50051')

    @patch('grpc.insecure_channel')
    def test_start_client_exception(self, mock_channel):
        """Test client startup with exception."""
        # Configure mock to raise exception
        mock_channel.side_effect = Exception("Connection error")
        
        # Create client and start it (should catch exception)
        client_obj = client.Client("localhost", 50051)
        client_obj.start_client("localhost", 50051)
        
        # Verify channel was attempted
        mock_channel.assert_called_once_with('localhost:50051')
        # No assertions needed for the caught exception, as we're just making sure it doesn't crash


# =========================================================================
# Additional Tests for Client to improve coverage
# =========================================================================
class TestClientAdditional:
    def test_send_message_with_unset_recipient(self):
        """Test sending a message when recipient is not set."""
        client_obj = client.Client("localhost", 50051)
        # Ensure recipient is not set
        if hasattr(client_obj, "recipient"):
            delattr(client_obj, "recipient")
        
        # Call with empty values
        result = client_obj.send_messages("", "Test message")
        assert result is False


# =========================================================================
# Main entry point for pytest
# =========================================================================
if __name__ == "__main__":
    sys.exit(pytest.main([
        "-v",
        "--cov=client",
        "--cov=server",
        __file__
    ]))