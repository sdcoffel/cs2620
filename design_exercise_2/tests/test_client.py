import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import io
import queue
import random
import socket
import threading
import time
import os
import pytest

from client import (
    receive_messages,
    process_network_queue,
    simulate_client,
)

# --- Helper: FakeSocket ---
class FakeSocket:
    """A fake socket to simulate recv, send, connect, and close behavior."""
    def __init__(self, responses=None):
        # responses is a list of bytes that recv() will return sequentially.
        self.responses = responses or []
        self.sent_data = []
        self.connected_address = None

    def recv(self, bufsize):
        if self.responses:
            return self.responses.pop(0)
        # When there are no responses, simulate connection closed.
        return b""

    def send(self, data):
        self.sent_data.append(data)

    def connect(self, address):
        self.connected_address = address

    def close(self):
        pass

# --- Tests for receive_messages ---

def test_receive_messages_normal():
    """
    Test that receive_messages decodes a valid message and enqueues
    a disconnect message when no data is received.
    """
    net_queue = queue.Queue()
    fake_sock = FakeSocket(responses=[b"Hello, client", b""])
    receive_messages(fake_sock, net_queue)
    # First message: decoded text.
    msg1 = net_queue.get_nowait()
    assert msg1 == "Hello, client"
    # Second message: server disconnected.
    msg2 = net_queue.get_nowait()
    assert "Server disconnected." in msg2

def test_receive_messages_exception():
    """
    Test that if socket.recv raises an exception, an error message is enqueued.
    """
    net_queue = queue.Queue()
    class ExceptionSocket:
        def recv(self, bufsize):
            raise Exception("Test exception")
    fake_sock = ExceptionSocket()
    receive_messages(fake_sock, net_queue)
    msg = net_queue.get_nowait()
    assert "Error receiving message: Test exception" in msg

# --- Tests for process_network_queue ---
# We let threads sleep briefly so that they get scheduled.

def test_process_network_queue_receive(monkeypatch, capsys):
    """
    Test that when a message is waiting in the network queue, it is dequeued
    and a "Received:" event is logged.
    """
    net_queue = queue.Queue()
    net_queue.put("Test message from network")
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]

    # Store the real sleep so we can call it inside our patched version.
    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda duration: real_sleep(0.01))
    # Fix the global time to a constant.
    monkeypatch.setattr(time, "strftime", lambda fmt, t: "2025-03-03 12:00:00")
    
    t = threading.Thread(
        target=process_network_queue,
        args=(net_queue, 10, clock, fake_log_file, fake_sock, other_recipients),
        daemon=True
    )
    t.start()
    # Wait a short time so the thread can process the queue
    real_sleep(0.05)
    
    # Capture console and log output
    captured = capsys.readouterr().out
    log_contents = fake_log_file.getvalue()
    
    # We expect "Received: Test message from network"
    assert ("Received: Test message from network" in captured or
            "Received: Test message from network" in log_contents)

def test_process_network_queue_send(monkeypatch, capsys):
    """
    Test that when the network queue is empty and random.randint returns 1,
    process_network_queue sends a message to the first recipient.
    """
    net_queue = queue.Queue()  # Start with an empty queue.
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]

    # Again, store the real sleep
    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda duration: real_sleep(0.01))
    monkeypatch.setattr(time, "strftime", lambda fmt, t: "2025-03-03 12:00:00")
    # Force the sending branch (rand_val == 1).
    monkeypatch.setattr(random, "randint", lambda a, b: 1)

    t = threading.Thread(
        target=process_network_queue,
        args=(net_queue, 10, clock, fake_log_file, fake_sock, other_recipients),
        daemon=True
    )
    t.start()
    real_sleep(0.05)
    
    # Check that something was sent
    assert fake_sock.sent_data, "Expected a message to be sent"
    sent_message = fake_sock.sent_data[0].decode('utf-8')
    # Expect "b" or "c" (the first entry in other_recipients) to be in that message
    assert other_recipients[0] in sent_message
    
    captured = capsys.readouterr().out
    log_contents = fake_log_file.getvalue()
    assert ("Sent to" in captured or "Sent to" in log_contents)

# --- Tests for simulate_client ---

def test_simulate_client(monkeypatch, tmp_path):
    """
    Test simulate_client by patching the socket, file I/O, and os._exit so that
    the simulation runs quickly without actually exiting the test process.
    """
    fake_sock = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: fake_sock)
    
    # Patch os._exit so that it raises an exception instead (so we can catch it in the test).
    def fake_exit(code):
        raise SystemExit(code)
    monkeypatch.setattr(os, "_exit", fake_exit)
    
    with pytest.raises(SystemExit):
        simulate_client("a", "localhost", 12345, simulation_duration=1)
    
    # Check that the client sent its username on connect.
    sent_usernames = [data for data in fake_sock.sent_data if b"a" in data]
    assert sent_usernames, "Expected the client to send its username on connect"
