import sys
sys.path.append("../")
import unittest
from unittest.mock import patch, MagicMock
import queue
import re


import chatapp_pb2
import chatapp_pb2_grpc
from server import ChatServer, active_clients, pending_messages, FILE_PATH, PENDING_MESSAGES_FILE_PATH

#these will need to be completely new with the new wire protocol

# A simple fake context for our RPC calls.
class FakeContext:
    def is_active(self):
        return False


class TestChatServer(unittest.TestCase):
    def setUp(self):
        # Reset the global dictionaries so tests start fresh.
        active_clients.clear()
        pending_messages.clear()
        self.server = ChatServer()


    @patch("server.load_accounts")
    @patch("server.create_account")
    def test_Login_new_account(self, mock_create_account, mock_load_accounts):
        # Simulate an empty accounts database.
        mock_load_accounts.return_value = {}
        request = chatapp_pb2.LoginRequest(username="newuser", password="hashedpass", is_new=True)
        fake_context = FakeContext()
        response = self.server.Login(request, fake_context)
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Account created! You are now logged in.")
        mock_create_account.assert_called_once_with("newuser", "hashedpass", FILE_PATH)


    @patch("server.load_accounts")
    def test_Login_existing_account_success(self, mock_load_accounts):
        # Simulate an existing account with matching password.
        mock_load_accounts.return_value = {"existinguser": {"password": "hashedpass"}}
        request = chatapp_pb2.LoginRequest(username="existinguser", password="hashedpass", is_new=False)
        fake_context = FakeContext()
        response = self.server.Login(request, fake_context)
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Success! You are now logged in.")


    @patch("server.load_accounts")
    def test_Login_existing_account_failure(self, mock_load_accounts):
        # Simulate an account where the provided password doesn't match.
        mock_load_accounts.return_value = {"existinguser": {"password": "otherpass"}}
        request = chatapp_pb2.LoginRequest(username="existinguser", password="hashedpass", is_new=False)
        fake_context = FakeContext()
        response = self.server.Login(request, fake_context)
        self.assertFalse(response.success)
        self.assertEqual(response.message, "This username/password is not registered with us!")


    @patch("server.load_pending_messages")
    @patch("server.delete_pending_messages")
    def test_GetPendingMessages(self, mock_delete_pending, mock_load_pending):
        # Simulate pending messages for the user "tester".
        fake_pending = {"tester": [("user1", "Hello"), ("user2", "Hi")]}
        mock_load_pending.return_value = fake_pending
        request = chatapp_pb2.PendingMessagesRequest(username="tester")
        fake_context = FakeContext()
        response = self.server.GetPendingMessages(request, fake_context)
        self.assertIn("user1: Hello", response.message)
        self.assertIn("user2: Hi", response.message)
        self.assertEqual(len(response.messages), 2)
        mock_delete_pending.assert_called_once_with(PENDING_MESSAGES_FILE_PATH, "tester", 10)


    @patch("server.delete_pending_messages")
    def test_MoreMessages(self, mock_delete_pending):
        # Prepopulate pending_messages for "tester".
        pending_messages["tester"] = [("user1", "Message1"), ("user2", "Message2"), ("user3", "Message3")]
        request = chatapp_pb2.MoreMessagesRequest(username="tester")
        fake_context = FakeContext()
        response = self.server.MoreMessages(request, fake_context)
        self.assertEqual(len(response.messages), 3)
        self.assertEqual(response.message, "More messages retrieved.\n")
        mock_delete_pending.assert_called_once_with(PENDING_MESSAGES_FILE_PATH, "tester", 10)


    def test_SendMessage_online(self):
        # Simulate recipient "receiver" is online with an active queue.
        q = queue.Queue()
        active_clients["receiver"] = q
        request = chatapp_pb2.SendMessageRequest(sender="sender", recipient="receiver", message="Hello")
        fake_context = FakeContext()
        response = self.server.SendMessage(request, fake_context)
        self.assertTrue(response.delivered)
        self.assertEqual(response.message, "Message delivered.")
        self.assertEqual(q.get(), ("sender", "Hello"))


    @patch("server.save_pending_messages")
    def test_SendMessage_offline(self, mock_save_pending):
        # Simulate recipient "receiver" is offline.
        request = chatapp_pb2.SendMessageRequest(sender="sender", recipient="receiver", message="Hello")
        fake_context = FakeContext()
        response = self.server.SendMessage(request, fake_context)
        self.assertFalse(response.delivered)
        self.assertEqual(response.message, "Recipient offline. Message saved as pending.")
        self.assertIn("receiver", pending_messages)
        self.assertIn(("sender", "Hello"), pending_messages["receiver"])
        mock_save_pending.assert_called_once()


    def test_ReceiveMessages(self):
        # Simulate a streaming response: populate the user's queue.
        q = queue.Queue()
        q.put(("user1", "Stream message"))
        active_clients["tester"] = q
        request = chatapp_pb2.ReceiveMessagesRequest(username="tester")

        # Define a fake context that stops streaming once the queue is empty.
        class FakeStreamContext:
            def is_active(self):
                return not q.empty()
            
        fake_context = FakeStreamContext()
        generator = self.server.ReceiveMessages(request, fake_context)
        messages = list(generator)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].sender, "user1")
        self.assertEqual(messages[0].message, "Stream message")



    @patch("server.load_pending_messages")
    @patch("server.delete_pending_messages")
    @patch("server.delete_account")
    def test_DeleteAccount_pending_no_confirm(self, mock_delete_account, mock_delete_pending, mock_load_pending):
        # Simulate that there are pending messages and deletion has not been confirmed.
        mock_load_pending.return_value = {"tester": [("user1", "Hello")]}
        request = chatapp_pb2.DeleteAccountRequest(username="tester", confirm=False)
        fake_context = FakeContext()
        response = self.server.DeleteAccount(request, fake_context)
        self.assertFalse(response.success)
        self.assertEqual(response.message, "You have unread messages. Confirm deletion to proceed.")
        mock_delete_account.assert_not_called()


    @patch("server.load_pending_messages")
    @patch("server.delete_pending_messages")
    @patch("server.delete_account")
    def test_DeleteAccount_pending_confirm(self, mock_delete_account, mock_delete_pending, mock_load_pending):
        # Simulate that there are pending messages and deletion is confirmed.
        mock_load_pending.return_value = {"tester": [("user1", "Hello"), ("user2", "Hi")]}
        request = chatapp_pb2.DeleteAccountRequest(username="tester", confirm=True)
        fake_context = FakeContext()
        response = self.server.DeleteAccount(request, fake_context)
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Account deletion successful.")
        mock_delete_account.assert_called_once_with("tester", FILE_PATH)
        mock_delete_pending.assert_called_once_with(PENDING_MESSAGES_FILE_PATH, "tester", 2)


    @patch("server.list_accounts")
    def test_ListAccounts(self, mock_list_accounts):
        # Simulate list_accounts returning a newline-separated string.
        mock_list_accounts.return_value = "user1\nuser2\nuser3\n"
        request = chatapp_pb2.ListAccountsRequest(filter="all")
        fake_context = FakeContext()
        response = self.server.ListAccounts(request, fake_context)
        self.assertEqual(response.accounts, ["user1", "user2", "user3"])
        self.assertEqual(response.message, "Accounts listed successfully.")
        mock_list_accounts.assert_called_once_with(FILE_PATH)

class CustomTestRunner(unittest.TextTestRunner):
    """Custom test runner with enhanced verbosity and summary output."""
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
    suite = unittest.TestLoader().loadTestsFromTestCase(TestChatServer)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)
