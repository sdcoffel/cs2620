import sys
import os
import threading
import queue
import time
import random
import socket
import io
import pytest


# Adjust system path to import the client module from the parent directory.
sys.path.append("../")
from client import receive_messages, process_network_queue, simulate_client

# ------------------------------------------------------------------
# Fake Socket Implementation for Testing
# ------------------------------------------------------------------

class FakeSocket:
    """A fake socket that records data sent via send() and optionally raises on send."""
    def __init__(self, raise_on_send=False):
        self.sent_data = []
        self.raise_on_send = raise_on_send

    def send(self, data):
        if self.raise_on_send:
            raise Exception("Simulated send failure")
        self.sent_data.append(data)

    def recv(self, bufsize):
        return b""

    def connect(self, addr):
        pass

# ------------------------------------------------------------------
# Helpers for controlling the infinite loop in process_network_queue
# ------------------------------------------------------------------
def fake_sleep_factory(max_calls, stop_exception=KeyboardInterrupt):
    """Returns a fake sleep function that allows max_calls then raises an exception."""
    call_count = [0]
    def fake_sleep(duration):
        call_count[0] += 1
        if call_count[0] >= max_calls:
            raise stop_exception
    return fake_sleep

# ------------------------------------------------------------------
# Tests for receive_messages (covers missing lines 60-65)
# ------------------------------------------------------------------

def test_receive_messages_disconnect():
    """
    Test that when the socket returns empty bytes, 
    receive_messages enqueues "Server disconnected." and exits.
    """
    class FakeSocketDisconnect:
        def recv(self, bufsize):
            return b""
    fake_sock = FakeSocketDisconnect()
    net_queue = queue.Queue()
    
    t = threading.Thread(target=receive_messages, args=(fake_sock, net_queue))
    t.start()
    t.join(timeout=1)
    
    # Verify that the disconnect message is enqueued.
    result = net_queue.get_nowait()
    assert result == "Server disconnected."

def test_receive_messages_exception():
    """
    Test that when the socket raises an exception, 
    receive_messages enqueues an error message and exits.
    """
    class FakeSocketException:
        def recv(self, bufsize):
            raise Exception("Test exception")
    fake_sock = FakeSocketException()
    net_queue = queue.Queue()
    
    t = threading.Thread(target=receive_messages, args=(fake_sock, net_queue))
    t.start()
    t.join(timeout=1)
    
    result = net_queue.get_nowait()
    assert result.startswith("Error receiving message: Test exception")

# ------------------------------------------------------------------
# Tests for process_network_queue - forcing each branch via random.randint
# ------------------------------------------------------------------

def test_process_network_queue_message_received(monkeypatch):
    """
    Test the branch when the network queue is not empty.
    This should log a "Message received" event.
    """
    net_queue = queue.Queue()
    net_queue.put("Test received message")
    log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]
    clock_rate = 1  # tick_interval = 1 second

    # Allow one tick then stop.
    monkeypatch.setattr(time, "sleep", fake_sleep_factory(max_calls=2))
    with pytest.raises(KeyboardInterrupt):
        process_network_queue(net_queue, clock_rate, log_file, fake_sock, other_recipients)
    
    log_contents = log_file.getvalue()
    assert "Message received" in log_contents, "Expected log entry for a received message."

def test_process_network_queue_rand_val_1(monkeypatch):
    """
    Test the branch for rand_val == 1.
    Expect: a message sent to the first recipient and a log entry addressed to the second.
    """
    net_queue = queue.Queue()  # empty queue triggers the random branch
    log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]
    clock_rate = 1

    # Force random.randint to return 1.
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    monkeypatch.setattr(time, "sleep", fake_sleep_factory(max_calls=2))
    
    with pytest.raises(KeyboardInterrupt):
        process_network_queue(net_queue, clock_rate, log_file, fake_sock, other_recipients)
    
    # Verify that a send occurred.
    assert len(fake_sock.sent_data) >= 1, "Expected a send call for rand_val == 1."
    sent_message = fake_sock.sent_data[0].decode('utf-8')
    assert sent_message.startswith(f"{other_recipients[0]}::Machine logical clock time:"), \
        "Expected a message with machine clock info."
    log_contents = log_file.getvalue()
    assert f"Message sent to {other_recipients[1]}" in log_contents, \
        "Expected log entry for sending to second recipient."

def test_process_network_queue_rand_val_2(monkeypatch):
    """
    Test the branch for rand_val == 2.
    Expect: a message sent to the second recipient (if available) and corresponding log entry.
    """
    net_queue = queue.Queue()  # empty queue to force random branch
    log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]
    clock_rate = 1

    # Force random.randint to return 2.
    monkeypatch.setattr(random, "randint", lambda a, b: 2)
    monkeypatch.setattr(time, "sleep", fake_sleep_factory(max_calls=2))
    
    with pytest.raises(KeyboardInterrupt):
        process_network_queue(net_queue, clock_rate, log_file, fake_sock, other_recipients)
    
    # Verify that a send call was made.
    assert len(fake_sock.sent_data) >= 1, "Expected a send call for rand_val == 2."
    sent_message = fake_sock.sent_data[0].decode('utf-8')
    assert sent_message.startswith(f"{other_recipients[1]}::Logical clock time:"), \
        "Expected a message with logical clock time for rand_val == 2."
    log_contents = log_file.getvalue()
    assert f"Message sent to {other_recipients[1]}" in log_contents, \
        "Expected log entry for sending to second recipient."

def test_process_network_queue_rand_val_3(monkeypatch):
    """
    Test the branch for rand_val == 3.
    Expect: messages sent to all recipients and a log entry indicating sending to all.
    """
    net_queue = queue.Queue()  # empty queue forces the random branch
    log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]
    clock_rate = 1

    # Force random.randint to return 3.
    monkeypatch.setattr(random, "randint", lambda a, b: 3)
    monkeypatch.setattr(time, "sleep", fake_sleep_factory(max_calls=2))
    
    with pytest.raises(KeyboardInterrupt):
        process_network_queue(net_queue, clock_rate, log_file, fake_sock, other_recipients)
    
    # Expect a send for each recipient.
    assert len(fake_sock.sent_data) >= len(other_recipients), \
        "Expected sends for all recipients for rand_val == 3."
    log_contents = log_file.getvalue()
    assert "Message sent to all other recipients" in log_contents, \
        "Expected log entry for sending to all recipients."

def test_process_network_queue_rand_val_else(monkeypatch):
    """
    Test the branch for any other random value (e.g. 4).
    Expect: no send call and a log entry for an internal event.
    """
    net_queue = queue.Queue()  # empty queue forces random branch
    log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]
    clock_rate = 1

    # Force random.randint to return 4 (or any value not 1, 2, 3).
    monkeypatch.setattr(random, "randint", lambda a, b: 4)
    monkeypatch.setattr(time, "sleep", fake_sleep_factory(max_calls=2))
    
    with pytest.raises(KeyboardInterrupt):
        process_network_queue(net_queue, clock_rate, log_file, fake_sock, other_recipients)
    
    # In this branch, no send should occur.
    assert len(fake_sock.sent_data) == 0, "No send expected for internal event branch."
    log_contents = log_file.getvalue()
    assert "Internal event occurred" in log_contents, "Expected log entry for internal event."

# ------------------------------------------------------------------
# Test for simulate_client
# ------------------------------------------------------------------

def test_simulate_client(monkeypatch):
    """
    Test simulate_client to ensure it preloads messages, sends the username,
    and writes the simulation header.
    """
    logs = {}
    def fake_open(filename, mode):
        logs[filename] = io.StringIO()
        return logs[filename]
    monkeypatch.setattr("builtins.open", fake_open)
    
    # Create a fake socket to capture sent data.
    fake_socket_instance = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: fake_socket_instance)
    
    # Override time.sleep to avoid delays.
    monkeypatch.setattr(time, "sleep", lambda duration: None)
    
    # Control randomness so that preloaded message count and clock_rate are predictable.
    monkeypatch.setattr(random, "randint", lambda a, b: 2)
    # Force random.choice to always pick the first element.
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    
    # Call simulate_client with a short simulation duration and a specified run_number.
    simulate_client("a", "localhost", 12345, simulation_duration=0.1, run_number=1)
    
    # Check that the log file for client 'a' contains the simulation header.
    log_content = logs["log_a.txt"].getvalue()
    assert "Simulation Run 1 START" in log_content, "Expected simulation header in log file."
    
    # Verify that the client sent its username.
    sent_data = b"".join(fake_socket_instance.sent_data)
    assert b"a" in sent_data, "Expected the client to send its username to the server."


#note: we are not testing the driver code, as that simply calls the rest of these functions. 
#so yes, technically we are testing all the functionality of the client, but only about 2/3 of the client code is actually being run here
#we thought it would be quite redundant to test the driver code.