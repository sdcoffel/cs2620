import sys
import os
import threading
import queue
import time
import socket

# Adjust system path to import the server module from the parent directory.
sys.path.append("../")  # Change this if your server script is in a different directory.

# Import the server functions and global active_clients.
from server import SendMessage, ReceiveMessages, handle_client, start_server, active_clients

# --------------------------
# Fake Connection and Socket
# --------------------------
class FakeConn:
    def __init__(self, responses):
        # responses: a list of strings to be returned on successive recv calls.
        self.responses = responses
        self.index = 0
        self.sent_data = []
        self.closed = False

    def recv(self, bufsize):
        if self.index < len(self.responses):
            response = self.responses[self.index]
            self.index += 1
            return response.encode('utf-8')
        return b""

    def sendall(self, data):
        self.sent_data.append(data)

    def close(self):
        self.closed = True

# Fake server socket for testing start_server.
class FakeServerSocket:
    def __init__(self):
        self.accepted = False

    def bind(self, addr):
        pass

    def listen(self):
        pass

    def accept(self):
        # Return a fake connection on first call, then raise KeyboardInterrupt.
        if not self.accepted:
            self.accepted = True
            # For simplicity, simulate a client that sends username "a" then disconnects.
            fake_conn = FakeConn(["a", ""])  # username then immediate disconnect
            return (fake_conn, ("127.0.0.1", 12345))
        raise KeyboardInterrupt

    def close(self):
        pass

# --------------------------
# Tests for SendMessage
# --------------------------
def test_SendMessage():
    # Prepare active_clients for recipient "b".
    recipient_queue = queue.Queue()
    active_clients["b"] = {"conn": FakeConn([]), "queue": recipient_queue}
    
    # Call SendMessage from "a" to "b" with a sample message.
    status = SendMessage("a", "b", "Hello")
    # Check that the message was enqueued.
    queued_sender, queued_message = recipient_queue.get_nowait()
    assert queued_sender == "a"
    assert queued_message == "Hello"
    # Depending on your implementation, adjust expected status.
    assert status in ["Message delivered.", "Message delivered successfully."]
    
    # Cleanup.
    del active_clients["b"]

# --------------------------
# Tests for ReceiveMessages
# --------------------------
def test_ReceiveMessages(monkeypatch, capsys):
    username = "testuser"
    # Create a fake connection whose sendall will raise an exception to break the infinite loop.
    class FakeConnError:
        def __init__(self):
            self.sent_data = []
        def sendall(self, data):
            self.sent_data.append(data)
            raise Exception("Simulated send error")
        def close(self):
            pass

    # Setup active_clients for testuser.
    fake_queue = queue.Queue()
    fake_queue.put(("sender", "Test message"))
    active_clients[username] = {'conn': FakeConnError(), 'queue': fake_queue}
    
    # Run ReceiveMessages in a separate thread; it should process one message then break.
    t = threading.Thread(target=ReceiveMessages, args=(username,), daemon=True)
    t.start()
    t.join(timeout=1)
    
    captured = capsys.readouterr().out
    assert f"Error sending message to {username}:" in captured
    
    # Cleanup.
    del active_clients[username]

# --------------------------
# Tests for handle_client
# --------------------------
def test_handle_client(monkeypatch):
    """
    Simulate a client that sends:
      1. Its username ("a")
      2. A valid message ("b::Hello")
      3. An invalid message ("invalid")
      4. An empty message to simulate disconnect.
    """
    responses = ["a", "b::Hello", "invalid", ""]
    fake_conn = FakeConn(responses)
    addr = ("127.0.0.1", 12345)
    
    # Pre-populate active_clients for recipient "b" so SendMessage works.
    active_clients["b"] = {"conn": FakeConn([]), "queue": queue.Queue()}
    
    # Run handle_client (this will block until the connection sends empty data).
    handle_client(fake_conn, addr)
    
    # After disconnection, client "a" should be removed from active_clients.
    assert "a" not in active_clients
    
    # Check that an error message was sent for the invalid format.
    error_sent = any("Invalid message format" in sent.decode('utf-8') for sent in fake_conn.sent_data)
    assert error_sent
    
    # Check that the valid message was delivered to recipient "b".
    q = active_clients["b"]["queue"]
    delivered = q.get_nowait()
    assert delivered == ("a", "Hello")
    
    # Cleanup.
    del active_clients["b"]

# --------------------------
# Test for start_server
# --------------------------
def test_start_server(monkeypatch):
    """
    Replace socket.socket with our FakeServerSocket so that start_server
    processes one connection and then raises KeyboardInterrupt.
    """
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: FakeServerSocket())
    
    # Since start_server catches KeyboardInterrupt internally, we run it in a thread.
    server_thread = threading.Thread(target=start_server)
    server_thread.start()
    # Allow some time for the server to process the fake connection.
    time.sleep(0.2)
    # The FakeServerSocket will raise KeyboardInterrupt on the second accept,
    # so the server should shut down gracefully.
    server_thread.join(timeout=1)
    assert not server_thread.is_alive()
