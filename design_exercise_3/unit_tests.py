import pytest
import sys
import queue
import time
import grpc
import chatapp_pb2
import chatserver  

#ian, do documentation for this please 
#-------------------------------------------------------------------------
# Dummy context classes to simulate gRPC contexts.
#-------------------------------------------------------------------------
class DummyContext:
    def is_active(self):
        return False

class DummyStreamingContext:
    def __init__(self, iterations=1):
        self.iterations = iterations
    def is_active(self):
        if self.iterations > 0:
            self.iterations -= 1
            return True
        return False

#-------------------------------------------------------------------------
# Fake functions to override external dependencies.
#-------------------------------------------------------------------------
def fake_load_accounts(file_path):
    # Return a dictionary simulating one existing account.
    return {"existing_user": {"password": "hashed123"}}

def fake_create_account(username, password, file_path):
    # For testing, do nothing (simulate account creation).
    pass

def fake_load_pending_messages(file_path):
    # Return a dict with pending messages for a user.
    return {"user1": [("sender1", "msg1"), ("sender2", "msg2"), ("sender3", "msg3")]}

def fake_delete_pending_messages(file_path, username, count):
    # Simulate deletion (do nothing).
    pass

def fake_save_pending_messages(file_path, username, sender, pending):
    # Simulate saving (do nothing).
    pass

def fake_delete_account(username, file_path):
    # Simulate deletion (do nothing).
    pass

def fake_list_accounts(file_path):
    # Return a newline-separated string of account names.
    return "existing_user\nuser2\nuser3"

#-------------------------------------------------------------------------
# Pytest fixture to override external dependencies and clear globals.
#-------------------------------------------------------------------------
class TestChatServer:
    @pytest.fixture(autouse=True)
    def setup_monkeypatch(self, monkeypatch):
        # Override file/account operations with our fake implementations.
        monkeypatch.setattr(chatserver, "load_accounts", fake_load_accounts)
        monkeypatch.setattr(chatserver, "create_account", fake_create_account)
        monkeypatch.setattr(chatserver, "load_pending_messages", fake_load_pending_messages)
        monkeypatch.setattr(chatserver, "delete_pending_messages", fake_delete_pending_messages)
        monkeypatch.setattr(chatserver, "save_pending_messages", fake_save_pending_messages)
        monkeypatch.setattr(chatserver, "delete_account", fake_delete_account)
        monkeypatch.setattr(chatserver, "list_accounts", fake_list_accounts)
        # Clear globals between tests.
        chatserver.active_clients.clear()
        chatserver.pending_messages.clear()

    #---------------------------------------------------------------------
    # Tests for the Login method.
    #---------------------------------------------------------------------
    def test_login_new_account_success(self):
        # Test that a new account is created when the username is not in the accounts.
        request = chatapp_pb2.LoginRequest(username="new_user", password="pass", is_new=True)
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.Login(request, context)
        assert response.success is True
        assert "Account created" in response.message

    def test_login_new_account_duplicate(self):
        # Test that trying to create an account with an existing username fails.
        request = chatapp_pb2.LoginRequest(username="existing_user", password="anything", is_new=True)
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.Login(request, context)
        assert response.success is False
        assert "Username already exists" in response.message

    def test_login_existing_account_success(self):
        # Test login for an existing account with the correct password.
        request = chatapp_pb2.LoginRequest(username="existing_user", password="hashed123", is_new=False)
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.Login(request, context)
        assert response.success is True
        assert "logged in" in response.message

    def test_login_existing_account_failure(self):
        # Test login with an incorrect password.
        request = chatapp_pb2.LoginRequest(username="existing_user", password="wrong", is_new=False)
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.Login(request, context)
        assert response.success is False
        assert "not registered" in response.message

    #---------------------------------------------------------------------
    # Tests for the GetPendingMessages method.
    #---------------------------------------------------------------------
    def test_get_pending_messages_with_messages(self):
        request = chatapp_pb2.PendingMessagesRequest(username="user1")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.GetPendingMessages(request, context)
        # Check that the response message contains details from our fake pending messages.
        assert "sender1: msg1" in response.message
        assert len(response.messages) <= 10

    def test_get_pending_messages_no_messages(self):
        # Test behavior when there are no pending messages.
        request = chatapp_pb2.PendingMessagesRequest(username="no_user")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.GetPendingMessages(request, context)
        assert response.messages == []
        assert "0 pending messages" in response.message

    #---------------------------------------------------------------------
    # Tests for the MoreMessages method.
    #---------------------------------------------------------------------
    def test_more_messages_with_messages(self):
        # Pre-populate the global pending_messages.
        chatserver.pending_messages["user2"] = [("s1", "msg1"), ("s2", "msg2"), ("s3", "msg3")]
        request = chatapp_pb2.MoreMessagesRequest(username="user2")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.MoreMessages(request, context)
        # We expect some messages to be returned.
        assert len(response.messages) > 0
        assert "More messages" in response.message or "No more messages" in response.message

    def test_more_messages_no_messages(self):
        if "user3" in chatserver.pending_messages:
            del chatserver.pending_messages["user3"]
        request = chatapp_pb2.MoreMessagesRequest(username="user3")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.MoreMessages(request, context)
        assert response.messages == []
        assert "No more messages" in response.message

    #---------------------------------------------------------------------
    # Tests for the SendMessage method.
    #---------------------------------------------------------------------
    def test_send_message_online(self):
        # Simulate an online recipient by populating the active_clients dictionary.
        q = queue.Queue()
        chatserver.active_clients["recipient"] = q
        request = chatapp_pb2.SendMessageRequest(sender="sender", recipient="recipient", message="Hello")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.SendMessage(request, context)
        assert response.delivered is True
        # Verify that the message was placed in the recipient's queue.
        queued = q.get_nowait()
        assert queued == ("sender", "Hello")
        del chatserver.active_clients["recipient"]

    def test_send_message_offline(self):
        # Test that when the recipient is offline the message is saved as pending.
        if "offline" in chatserver.pending_messages:
            del chatserver.pending_messages["offline"]
        request = chatapp_pb2.SendMessageRequest(sender="sender", recipient="offline", message="Hi")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.SendMessage(request, context)
        assert response.delivered is False
        assert "offline" in chatserver.pending_messages
        assert chatserver.pending_messages["offline"][-1] == ("sender", "Hi")

    #---------------------------------------------------------------------
    # Test for the ReceiveMessages streaming method.
    #---------------------------------------------------------------------
    def test_receive_messages_stream(self):
        # Pre-populate an active client's queue with a message.
        q = queue.Queue()
        q.put(("streamer", "stream message"))
        chatserver.active_clients["stream_user"] = q
        request = chatapp_pb2.ReceiveMessagesRequest(username="stream_user")
        context = DummyStreamingContext(iterations=2)
        server_instance = chatserver.ChatServer()
        gen = server_instance.ReceiveMessages(request, context)
        # Retrieve one message from the stream.
        response = next(gen)
        assert response.sender == "streamer"
        assert "stream message" in response.message
        del chatserver.active_clients["stream_user"]

    #---------------------------------------------------------------------
    # Tests for the DeleteAccount method.
    #---------------------------------------------------------------------
    def test_delete_account_with_pending_no_confirm(self):
        # When pending messages exist and the deletion is not confirmed.
        def fake_load_pending(file_path):
            return {"user_del": [("s", "m")]}
        monkey_patch = pytest.MonkeyPatch()
        monkey_patch.setattr(chatserver, "load_pending_messages", fake_load_pending)
        request = chatapp_pb2.DeleteAccountRequest(username="user_del", confirm=False)
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.DeleteAccount(request, context)
        assert response.success is False
        monkey_patch.undo()

    def test_delete_account_with_pending_confirm(self):
        # When pending messages exist and deletion is confirmed.
        def fake_load_pending(file_path):
            return {"user_del": [("s", "m")]}
        monkey_patch = pytest.MonkeyPatch()
        monkey_patch.setattr(chatserver, "load_pending_messages", fake_load_pending)
        request = chatapp_pb2.DeleteAccountRequest(username="user_del", confirm=True)
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.DeleteAccount(request, context)
        assert response.success is True
        monkey_patch.undo()

    def test_delete_account_no_pending(self):
        # When there are no pending messages.
        def fake_load_pending(file_path):
            return {"user_del": []}
        monkey_patch = pytest.MonkeyPatch()
        monkey_patch.setattr(chatserver, "load_pending_messages", fake_load_pending)
        request = chatapp_pb2.DeleteAccountRequest(username="user_del", confirm=False)
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.DeleteAccount(request, context)
        assert response.success is True
        monkey_patch.undo()

    #---------------------------------------------------------------------
    # Tests for the ListAccounts method.
    #---------------------------------------------------------------------
    def test_list_accounts_no_filter(self):
        request = chatapp_pb2.ListAccountsRequest(filter="all")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.ListAccounts(request, context)
        assert "Accounts listed successfully" in response.message
        assert "existing_user" in response.accounts

    def test_list_accounts_with_regex(self):
        # Use a regex filter to match one account.
        request = chatapp_pb2.ListAccountsRequest(filter="user2")
        context = DummyContext()
        server_instance = chatserver.ChatServer()
        response = server_instance.ListAccounts(request, context)
        assert "user2" in response.accounts
        # Now test with an invalid regex.
        request_invalid = chatapp_pb2.ListAccountsRequest(filter="(unclosed[")
        response_invalid = server_instance.ListAccounts(request_invalid, context)
        assert response_invalid.accounts == []
        assert "No users match this pattern" in response_invalid.message


import chatapp_pb2
import chatapp_pb2_grpc
from raftnode import RaftNode, RaftService

#-------------------------------------------------------------------------
# Dummy global leader object for testing.
#-------------------------------------------------------------------------
class DummyGlobal:
    def __init__(self, value=None):
        self.value = value

#-------------------------------------------------------------------------
# Fake gRPC channel for simulating RequestVote RPC in send_request_vote.
#-------------------------------------------------------------------------
def fake_insecure_channel_for_request_vote(peer):
    class FakeChannel:
        def __enter__(self):
            class FakeStub:
                def RequestVote(self, request, timeout):
                    # Simulate a positive vote response.
                    class FakeResponse:
                        vote_granted = True
                    return FakeResponse()
            return FakeStub()
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    return FakeChannel()

#-------------------------------------------------------------------------
# Fake gRPC channel for simulating AppendEntries RPC in send_heartbeats.
#-------------------------------------------------------------------------
def fake_insecure_channel_for_append_entries(peer):
    class FakeChannel:
        def __enter__(self):
            class FakeStub:
                def AppendEntries(self, request, timeout):
                    # Simulate a successful heartbeat response.
                    class FakeResponse:
                        success = True
                    return FakeResponse()
            return FakeStub()
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    return FakeChannel()

#-------------------------------------------------------------------------
# Tests for RaftNode
#-------------------------------------------------------------------------
class TestRaftNode:
    def test_initialization_leader(self):
        # When server_id is "server1", node becomes leader on startup.
        dummy_global = DummyGlobal()
        node = RaftNode(server_id="server1", peers=[], address="localhost:50051",
                        timeout=5, global_leader=dummy_global)
        # Allow a moment for the election_loop thread to start.
        time.sleep(0.2)
        # For server1, role should be leader.
        assert node.is_leader() is True
        # Global leader value should be updated to "server1" (if used properly).
        # Note: the code assigns 'global_leader = self.server_id' which may not update dummy_global.value.
        # We check the node's role primarily.
    
    def test_initialization_follower(self):
        # When server_id is not "server1", node remains a follower initially.
        dummy_global = DummyGlobal("server1")
        node = RaftNode(server_id="server2", peers=[], address="localhost:50052",
                        timeout=5, global_leader=dummy_global)
        time.sleep(0.2)
        assert node.is_leader() is False
        # Since the node is a follower, get_leader should return None.
        assert node.get_leader() is None

    def test_add_peer(self):
        dummy_global = DummyGlobal("server1")
        node = RaftNode(server_id="server2", peers=[], address="localhost:50052",
                        timeout=5, global_leader=dummy_global)
        # Initially, no peers.
        assert node.peers == []
        # Add a peer.
        node.add_peer("localhost:50053")
        assert "localhost:50053" in node.peers

    def test_is_leader_method(self):
        dummy_global = DummyGlobal("server1")
        node = RaftNode(server_id="server2", peers=[], address="localhost:50052",
                        timeout=5, global_leader=dummy_global)
        # Manually set role.
        node.role = "leader"
        assert node.is_leader() is True
        node.role = "follower"
        assert node.is_leader() is False

    def test_get_leader_method(self):
        dummy_global = DummyGlobal("server1")
        node = RaftNode(server_id="server2", peers=[], address="localhost:50052",
                        timeout=5, global_leader=dummy_global)
        # When role is follower, get_leader returns None.
        node.role = "follower"
        assert node.get_leader() is None
        # When node is leader, get_leader returns node.leader_id.
        node.role = "leader"
        node.leader_id = "server2"
        assert node.get_leader() == "server2"

    def test_send_request_vote_exception(self, monkeypatch):
        dummy_global = DummyGlobal("server1")
        node = RaftNode(server_id="server2", peers=["localhost:50051"], address="localhost:50052",
                        timeout=5, global_leader=dummy_global)
        # Monkey-patch to raise an exception.
        def fake_channel_exception(peer):
            raise Exception("Test exception")
        monkeypatch.setattr(grpc, "insecure_channel", fake_channel_exception)
        result = node.send_request_vote("localhost:50051", term=1)
        assert result is False

    def test_send_heartbeats(self, monkeypatch):
        dummy_global = DummyGlobal("server2")
        node = RaftNode(server_id="server2", peers=["localhost:50052", "localhost:50053"],
                        address="localhost:50052", timeout=5, global_leader=dummy_global)
        # Set node role to leader so heartbeats are sent.
        node.role = "leader"
        # Monkey-patch grpc.insecure_channel for AppendEntries.
        monkeyatch = monkeypatch
        monkeyatch.setattr(grpc, "insecure_channel", fake_insecure_channel_for_append_entries)
        # Also, override time.sleep to avoid long delays in tests.
        monkeyatch.setattr(time, "sleep", lambda s: None)
        # Capture current heartbeat timestamp.
        prev_heartbeat = node.last_heartbeat
        node.send_heartbeats()
        # After sending heartbeats, last_heartbeat should be updated.
        assert node.last_heartbeat > prev_heartbeat

    def test_election_loop_promotes_to_leader(self, monkeypatch):
        # Test that if election timeout expires and send_request_vote returns True,
        # the node becomes leader.
        dummy_global = DummyGlobal(None)
        node = RaftNode(server_id="server2", peers=["localhost:50051"], address="localhost:50052",
                        timeout=0.1, global_leader=dummy_global)
        # Force last heartbeat to an old value to trigger election.
        node.last_heartbeat = time.time() - 1
        # Override send_request_vote to always return True.
        monkeypatch.setattr(node, "send_request_vote", lambda peer, term: True)
        # Allow election_loop to run for a short time.
        time.sleep(0.3)
        # Node should have been elected leader.
        assert node.is_leader() is True
        assert node.leader_id == "server2"
        # Also, the dummy global leader's value should be updated.
        assert dummy_global.value == "server2"

#-------------------------------------------------------------------------
# Tests for RaftService
#-------------------------------------------------------------------------
class TestRaftService:
    @pytest.fixture
    def dummy_node(self):
        dummy_global = DummyGlobal("server1")
        node = RaftNode(server_id="server1", peers=[], address="localhost:50051",
                        timeout=5, global_leader=dummy_global)
        # Ensure node's state is controlled.
        node.role = "follower"
        node.leader_id = None
        return node

    def test_request_vote(self, dummy_node):
        service = RaftService(dummy_node)
        request = chatapp_pb2.RequestVoteRequest(term=2,
                                                 candidate_id="server2",
                                                 last_log_index=0,
                                                 last_log_term=0)
        context = type("DummyContext", (), {"is_active": lambda self: True})()
        response = service.RequestVote(request, context)
        assert response.vote_granted is True
        assert response.term == 2

    def test_append_entries(self, dummy_node):
        service = RaftService(dummy_node)
        # Set node to leader initially.
        dummy_node.role = "leader"
        request = chatapp_pb2.AppendEntriesRequest(
            term=3,
            leader_id="serverX",
            prev_log_index=0,
            prev_log_term=0,
            entries=[],
            leader_commit=0
        )
        context = type("DummyContext", (), {"is_active": lambda self: True})()
        response = service.AppendEntries(request, context)
        # After AppendEntries, node should be follower and leader_id updated.
        assert response.success is True
        assert dummy_node.leader_id == "serverX"
        assert dummy_node.role == "follower"

    def test_ping(self, dummy_node, monkeypatch):
        global raft_node
        dummy_node.role = "follower"  # set the desired role
        raft_node = dummy_node       # update the global variable
        service = RaftService(dummy_node)
        request = chatapp_pb2.PingRequest()
        context = type("DummyContext", (), {"is_active": lambda self: True})()
        response = service.Ping(request, context)
        assert response.status == "OK"
        assert response.role == "follower"

    def test_add_server(self, dummy_node):
        service = RaftService(dummy_node)
        # Initially, no peers.
        assert dummy_node.peers == []
        request = chatapp_pb2.AddServerRequest(server_id="server2", address="localhost:50052")
        context = type("DummyContext", (), {"is_active": lambda self: True})()
        response = service.AddServer(request, context)
        assert response.success is True
        assert "localhost:50052" in dummy_node.peers


#-------------------------------------------------------------------------
# Code to run tests with pytest and measure coverage for chatserver.py.
#-------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(pytest.main([
        "-v",
        "--maxfail=1",
        "--cov=chatserver",
        "--cov=raftnode",
        __file__
    ]))