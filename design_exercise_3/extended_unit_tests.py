import pytest
import os
import uuid
from datetime import datetime
import sys
from unittest.mock import MagicMock, patch, mock_open

# Import modules to test
import operations
import accounts
import messages
from config_manager import ConfigManager

# Test data paths - using temporary files to avoid affecting real data
TEST_ACCOUNTS_PATH = "test_accounts.txt"
TEST_MESSAGES_PATH = "test_messages.txt"
TEST_PENDING_MESSAGES_PATH = "test_pending_messages.txt"

# Clean up test files after tests
@pytest.fixture(autouse=True)
def cleanup():
    yield
    for file_path in [TEST_ACCOUNTS_PATH, TEST_MESSAGES_PATH, TEST_PENDING_MESSAGES_PATH]:
        if os.path.exists(file_path):
            os.remove(file_path)


# =========================================================================
# Tests for operations.py
# =========================================================================
class TestOperations:
    def test_serialize_account(self):
        """Test the serialization of account data to string format."""
        account = {
            "uuid": "test-uuid-1234",
            "username": "testuser",
            "password": "hashedpw123"
        }
        expected = "test-uuid-1234|testuser|hashedpw123\n"
        result = operations.serialize_account(account)
        assert result == expected

    def test_deserialize_account(self):
        """Test the deserialization of account string to dictionary."""
        line = "test-uuid-1234|testuser|hashedpw123\n"
        expected = {
            "uuid": "test-uuid-1234",
            "username": "testuser",
            "password": "hashedpw123"
        }
        result = operations.deserialize_account(line)
        assert result == expected


# =========================================================================
# Tests for accounts.py
# =========================================================================
class TestAccounts:
    def test_is_valid_account(self):
        """Test validation of account structure."""
        # Valid account
        valid_account = {
            "uuid": "test-uuid",
            "username": "testuser",
            "hashed_password": "hashedpw"
        }
        assert accounts.is_valid_account(valid_account) is True

        # Invalid account (missing key)
        invalid_account = {
            "uuid": "test-uuid",
            "username": "testuser"
            # Missing hashed_password
        }
        assert accounts.is_valid_account(invalid_account) is False

        # Invalid account (extra key)
        invalid_account2 = {
            "uuid": "test-uuid",
            "username": "testuser",
            "hashed_password": "hashedpw",
            "extra_field": "value"
        }
        assert accounts.is_valid_account(invalid_account2) is False

        # Not a dictionary
        assert accounts.is_valid_account("not a dict") is False

    @patch('accounts.load_accounts')
    @patch('accounts.save_accounts')
    def test_create_account(self, mock_save, mock_load):
        """Test account creation."""
        mock_load.return_value = {}  # No existing accounts
        
        # Test successful account creation
        accounts.create_account("newuser", "password123", TEST_ACCOUNTS_PATH)
        mock_save.assert_called_once()
        
        # Reset for next test
        mock_save.reset_mock()
        mock_load.return_value = {"existinguser": {"username": "existinguser"}}
        
        # Test duplicate username
        with pytest.raises(ValueError, match="Username already exists"):
            accounts.create_account("existinguser", "password123", TEST_ACCOUNTS_PATH)

    @patch('accounts.load_accounts')
    @patch('accounts.save_accounts')
    def test_delete_account(self, mock_save, mock_load):
        """Test account deletion."""
        mock_load.return_value = {"testuser": {"username": "testuser"}}
        
        # Test successful deletion
        accounts.delete_account("testuser", TEST_ACCOUNTS_PATH)
        mock_save.assert_called_once()
        
        # Reset for next test
        mock_save.reset_mock()
        mock_load.return_value = {}  # Empty accounts dictionary
        
        # Test deleting non-existent account
        with pytest.raises(ValueError, match="Username does not exist"):
            accounts.delete_account("nonexistent", TEST_ACCOUNTS_PATH)

    @patch('accounts.load_accounts')
    def test_list_accounts(self, mock_load):
        """Test listing all accounts."""
        mock_load.return_value = {
            "user1": {"username": "user1"},
            "user2": {"username": "user2"},
            "user3": {"username": "user3"}
        }
        
        result = accounts.list_accounts(TEST_ACCOUNTS_PATH)
        assert "user1" in result
        assert "user2" in result
        assert "user3" in result
        assert isinstance(result, str)


# =========================================================================
# Tests for messages.py
# =========================================================================
class TestMessages:
    def test_is_valid_message(self):
        """Test validation of message structure."""
        # Valid message
        valid_message = {
            "uuid": "test-uuid",
            "datetime": "2025-03-24T12:00:00",
            "sender": "sender1",
            "receiver": "receiver1",
            "content": "Hello, world!"
        }
        assert messages.is_valid_message(valid_message) is True

        # Invalid message (missing key)
        invalid_message = {
            "uuid": "test-uuid",
            "datetime": "2025-03-24T12:00:00",
            "sender": "sender1",
            "content": "Hello, world!"
            # Missing receiver
        }
        assert messages.is_valid_message(invalid_message) is False

        # Not a dictionary
        assert messages.is_valid_message("not a dict") is False

    def test_create_message(self):
        """Test message creation."""
        messages_dict = {}
        
        # Create a valid message
        result = messages.create_message(
            "sender1", "receiver1", "Test message", messages_dict
        )
        
        # Verify the message was created correctly
        assert "uuid" in result
        assert "datetime" in result
        assert result["sender"] == "sender1"
        assert result["receiver"] == "receiver1"
        assert result["content"] == "Test message"
        
        # Verify the message was stored in the dictionary
        uuid_key = result["uuid"]
        assert uuid_key in messages_dict
        assert messages_dict[uuid_key] == result

    def test_list_messages(self):
        """Test listing messages with and without filters."""
        # Create test messages dictionary
        test_messages = {
            "uuid1": {
                "uuid": "uuid1",
                "datetime": "2025-03-24T12:00:00",
                "sender": "alice",
                "receiver": "bob",
                "content": "Hi Bob"
            },
            "uuid2": {
                "uuid": "uuid2",
                "datetime": "2025-03-24T12:05:00",
                "sender": "bob",
                "receiver": "alice",
                "content": "Hi Alice"
            },
            "uuid3": {
                "uuid": "uuid3",
                "datetime": "2025-03-24T12:10:00",
                "sender": "charlie",
                "receiver": "alice",
                "content": "Hello Alice"
            }
        }
        
        # Test listing all messages
        all_msgs = messages.list_messages(test_messages)
        assert len(all_msgs) == 3
        assert all_msgs[0]["datetime"] <= all_msgs[1]["datetime"]  # Check sorting
        
        # Test filtering messages between specific users
        alice_bob_msgs = messages.list_messages(test_messages, "alice", "bob")
        assert len(alice_bob_msgs) == 2
        assert all(msg["sender"] in ["alice", "bob"] and 
                  msg["receiver"] in ["alice", "bob"] 
                  for msg in alice_bob_msgs)

    def test_format_datetime(self):
        """Test formatting of datetime strings."""
        dt_str = "2025-03-24T14:35:22.123456"
        formatted = messages.format_datetime(dt_str)
        assert formatted == "2025-03-24 14:35"

    @patch('builtins.open', new_callable=mock_open, read_data="uuid1,2025-03-24T12:00:00,sender1,receiver1,content1\nuuid2,2025-03-24T12:05:00,sender2,receiver2,content2")
    def test_load_messages(self, mock_file):
        """Test loading messages from a file."""
        result = messages.load_messages(TEST_MESSAGES_PATH)
        
        assert len(result) == 2
        assert "uuid1" in result
        assert result["uuid1"]["sender"] == "sender1"
        assert result["uuid2"]["content"] == "content2"

    @patch('builtins.open', new_callable=mock_open)
    def test_save_messages(self, mock_file):
        """Test saving messages to a file."""
        test_messages = {
            "uuid1": {
                "uuid": "uuid1",
                "datetime": "2025-03-24T12:00:00",
                "sender": "sender1",
                "receiver": "receiver1",
                "content": "content1"
            }
        }
        
        messages.save_messages(TEST_MESSAGES_PATH, test_messages)
        
        # Verify file was opened for writing
        mock_file.assert_called_once_with(TEST_MESSAGES_PATH, 'w')
        # Verify write was called with expected data
        handle = mock_file()
        handle.write.assert_called_once_with("uuid1|2025-03-24T12:00:00|sender1|receiver1|content1\n")

    @patch('messages.load_pending_messages')
    def test_has_pending_messages(self, mock_load):
        """Test checking for pending messages."""
        # User with pending messages
        mock_load.return_value = {"user1": [("sender1", "msg1")]}
        assert messages.has_pending_messages("user1", TEST_PENDING_MESSAGES_PATH) is True
        
        # User without pending messages
        assert messages.has_pending_messages("user2", TEST_PENDING_MESSAGES_PATH) is False
        
        # User with empty pending messages list
        mock_load.return_value = {"user3": []}
        assert messages.has_pending_messages("user3", TEST_PENDING_MESSAGES_PATH) is False

    @patch('builtins.open', new_callable=mock_open)
    def test_save_pending_messages(self, mock_file):
        """Test saving pending messages."""
        # Simple string message
        messages.save_pending_messages(TEST_PENDING_MESSAGES_PATH, "recipient1", "sender1", "Hello")
        handle = mock_file()
        handle.write.assert_called_with("recipient1|sender1|Hello\n")
        
        # Reset mock
        handle.write.reset_mock()
        
        # Test with a message dictionary
        test_dict = {"recipient2": [("sender2", "Hi there")]}
        messages.save_pending_messages(TEST_PENDING_MESSAGES_PATH, "recipient2", "sender2", test_dict)
        handle.write.assert_called_with("recipient2|sender2|Hi there\n")

    @patch('builtins.open', new_callable=mock_open, read_data="r1|s1|message1\nr1|s2|message2\nr2|s3|message3")
    def test_load_pending_messages(self, mock_file):
        """Test loading pending messages from a file."""
        result = messages.load_pending_messages(TEST_PENDING_MESSAGES_PATH)
        
        assert "r1" in result
        assert "r2" in result
        assert len(result["r1"]) == 2
        assert result["r1"][0] == ("s1", "message1")
        assert result["r2"][0] == ("s3", "message3")

    @patch('messages.load_pending_messages')
    @patch('builtins.open', new_callable=mock_open)
    def test_delete_pending_messages(self, mock_file, mock_load):
        """Test deleting pending messages."""
        # Set up mock data
        mock_load.return_value = {
            "user1": [("s1", "msg1"), ("s2", "msg2"), ("s3", "msg3")],
            "user2": [("s4", "msg4")]
        }
        
        # Delete the last two messages for user1
        messages.delete_pending_messages(TEST_PENDING_MESSAGES_PATH, "user1", 2)
        
        # Check that the file was opened for writing
        mock_file.assert_called_once_with(TEST_PENDING_MESSAGES_PATH, 'w')
        
        # Check write calls - only user1's first message and user2's message should remain
        handle = mock_file()
        handle.write.assert_any_call("user1|s1|msg1\n")
        handle.write.assert_any_call("user2|s4|msg4\n")
        
        # Only two writes should have occurred
        assert handle.write.call_count == 2


# =========================================================================
# Tests for config_manager.py
# =========================================================================
class TestConfigManager:
    @patch('config_manager.KazooClient')
    def test_init(self, mock_kazoo):
        """Test initialization of ConfigManager."""
        # Setup mock
        mock_client = MagicMock()
        mock_kazoo.return_value = mock_client
        
        # Create config manager
        cm = ConfigManager()
        
        # Verify KazooClient was created and started
        mock_kazoo.assert_called_once()
        mock_client.start.assert_called_once()
        assert cm.zk == mock_client

    @patch('config_manager.KazooClient')
    def test_register_server_new(self, mock_kazoo):
        """Test registering a new server."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.exists.return_value = False  # Node doesn't exist
        mock_kazoo.return_value = mock_client
        
        # Create config manager and register server
        cm = ConfigManager()
        cm.register_server("server1", "localhost:50051")
        
        # Verify create was called
        path = "/servers/server1"
        mock_client.exists.assert_called_with(path)
        mock_client.create.assert_called_with(path, b"localhost:50051")
        mock_client.set.assert_not_called()

    @patch('config_manager.KazooClient')
    def test_register_server_update(self, mock_kazoo):
        """Test updating an existing server."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.exists.return_value = True  # Node exists
        mock_kazoo.return_value = mock_client
        
        # Create config manager and register server
        cm = ConfigManager()
        cm.register_server("server1", "localhost:50051")
        
        # Verify set was called
        path = "/servers/server1"
        mock_client.exists.assert_called_with(path)
        mock_client.create.assert_not_called()
        mock_client.set.assert_called_with(path, b"localhost:50051")

    @patch('config_manager.KazooClient')
    def test_get_all_servers(self, mock_kazoo):
        """Test retrieving all servers."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.exists.return_value = True
        mock_client.get_children.return_value = ["server1", "server2"]
        
        # Mock get method to return different values for different servers
        def mock_get(path):
            if path == "/servers/server1":
                return (b"localhost:50051", None)
            elif path == "/servers/server2":
                return (b"localhost:50052", None)
        
        mock_client.get.side_effect = mock_get
        mock_kazoo.return_value = mock_client
        
        # Create config manager and get servers
        cm = ConfigManager()
        servers = cm.get_all_servers()
        
        # Verify results
        assert len(servers) == 2
        assert servers["server1"] == "localhost:50051"
        assert servers["server2"] == "localhost:50052"

    @patch('config_manager.KazooClient')
    def test_get_all_servers_no_servers(self, mock_kazoo):
        """Test retrieving servers when none exist."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.exists.return_value = False  # /servers doesn't exist
        mock_kazoo.return_value = mock_client
        
        # Create config manager and get servers
        cm = ConfigManager()
        servers = cm.get_all_servers()
        
        # Verify empty result
        assert servers == {}
        mock_client.get_children.assert_not_called()

    @patch('config_manager.KazooClient')
    def test_close(self, mock_kazoo):
        """Test closing the ConfigManager."""
        # Setup mock
        mock_client = MagicMock()
        mock_kazoo.return_value = mock_client
        
        # Create config manager and close it
        cm = ConfigManager()
        cm.close()
        
        # Verify calls
        mock_client.stop.assert_called_once()
        mock_client.close.assert_called_once()


# =========================================================================
# Main entry point for pytest
# =========================================================================
if __name__ == "__main__":
    sys.exit(pytest.main([
        "-v",
        "--cov=operations",
        "--cov=accounts",
        "--cov=messages",
        "--cov=config_manager",
        __file__
    ]))