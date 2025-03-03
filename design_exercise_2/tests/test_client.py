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
    def __init__(self, responses=None, raise_on_send=False, raise_on_connect=False):
        # responses is a list of bytes that recv() will return sequentially.
        self.responses = responses or []
        self.sent_data = []
        self.connected_address = None
        self.raise_on_send = raise_on_send
        self.raise_on_connect = raise_on_connect

    def recv(self, bufsize):
        if self.responses:
            return self.responses.pop(0)
        # When there are no responses, simulate connection closed.
        return b""

    def send(self, data):
        if self.raise_on_send:
            raise Exception("Test send exception")
        self.sent_data.append(data)

    def connect(self, address):
        if self.raise_on_connect:
            raise Exception("Test connect exception")
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

def test_process_network_queue_send_to_second_recipient(monkeypatch, capsys):
    """
    Test that when the network queue is empty and random.randint returns 2,
    process_network_queue sends a message to the second recipient.
    """
    net_queue = queue.Queue()  # Start with an empty queue.
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]

    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda duration: real_sleep(0.01))
    monkeypatch.setattr(time, "strftime", lambda fmt, t: "2025-03-03 12:00:00")
    # Force the sending branch for second recipient (rand_val == 2).
    monkeypatch.setattr(random, "randint", lambda a, b: 2)

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
    # Expect the second recipient in the message
    assert other_recipients[1] in sent_message
    
    captured = capsys.readouterr().out
    log_contents = fake_log_file.getvalue()
    assert ("Sent to" in captured or "Sent to" in log_contents)

def test_process_network_queue_send_to_all_recipients(monkeypatch, capsys):
    """
    Test that when the network queue is empty and random.randint returns 3,
    process_network_queue sends a message to all recipients.
    """
    net_queue = queue.Queue()  # Start with an empty queue.
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]

    # Run the function once with a controlled setup
    # Store the real sleep and create a counter to break after first iteration
    iterations_run = [0]
    real_sleep = time.sleep
    
    def fake_sleep(duration):
        iterations_run[0] += 1
        if iterations_run[0] > 1:
            # After first iteration, we'll exit the test
            raise Exception("Test complete")
        real_sleep(0.01)
        
    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(time, "strftime", lambda fmt, t: "2025-03-03 12:00:00")
    # Force the sending branch for all recipients (rand_val == 3).
    monkeypatch.setattr(random, "randint", lambda a, b: 3)

    with pytest.raises(Exception, match="Test complete"):
        process_network_queue(net_queue, 10, clock, fake_log_file, fake_sock, other_recipients)

    # Verify messages were sent to all recipients
    assert len(fake_sock.sent_data) >= len(other_recipients), "Expected at least one message per recipient"

    # Verify each recipient received at least one message
    for recipient in other_recipients:
        found = any(recipient in data.decode('utf-8') for data in fake_sock.sent_data)
        assert found, f"Expected to find message sent to {recipient}"

    # Verify log contains the right info
    log_contents = fake_log_file.getvalue()
    assert "Sent to" in log_contents
    assert all(recipient in log_contents for recipient in other_recipients), "All recipients should be in the log"

def test_process_network_queue_internal_event(monkeypatch, capsys):
    """
    Test that when the network queue is empty and random.randint returns > 3,
    process_network_queue logs an internal event.
    """
    net_queue = queue.Queue()  # Start with an empty queue.
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket()
    other_recipients = ["b", "c"]

    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda duration: real_sleep(0.01))
    monkeypatch.setattr(time, "strftime", lambda fmt, t: "2025-03-03 12:00:00")
    # Force the internal event branch (rand_val > 3).
    monkeypatch.setattr(random, "randint", lambda a, b: 4)

    t = threading.Thread(
        target=process_network_queue,
        args=(net_queue, 10, clock, fake_log_file, fake_sock, other_recipients),
        daemon=True
    )
    t.start()
    real_sleep(0.05)
    
    # No message should be sent
    assert not fake_sock.sent_data, "Did not expect any messages to be sent"
    
    captured = capsys.readouterr().out
    log_contents = fake_log_file.getvalue()
    assert ("Internal event occurred" in captured or "Internal event occurred" in log_contents)

def test_process_network_queue_send_exception_case1(monkeypatch, capsys):
    """
    Test error handling when send() raises an exception in process_network_queue (case 1 - first recipient).
    """
    net_queue = queue.Queue()  # Start with an empty queue.
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket(raise_on_send=True)
    other_recipients = ["b", "c"]

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
    
    # Check error was logged
    captured = capsys.readouterr().out
    assert "Error sending message: Test send exception" in captured

def test_process_network_queue_send_exception_case2(monkeypatch, capsys):
    """
    Test error handling when send() raises an exception in process_network_queue (case 2 - second recipient).
    """
    net_queue = queue.Queue()  # Start with an empty queue.
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket(raise_on_send=True)
    other_recipients = ["b", "c"]

    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda duration: real_sleep(0.01))
    monkeypatch.setattr(time, "strftime", lambda fmt, t: "2025-03-03 12:00:00")
    # Force the sending branch (rand_val == 2).
    monkeypatch.setattr(random, "randint", lambda a, b: 2)

    t = threading.Thread(
        target=process_network_queue,
        args=(net_queue, 10, clock, fake_log_file, fake_sock, other_recipients),
        daemon=True
    )
    t.start()
    real_sleep(0.05)
    
    # Check error was logged
    captured = capsys.readouterr().out
    assert "Error sending message: Test send exception" in captured

def test_process_network_queue_send_exception_case3(monkeypatch, capsys):
    """
    Test error handling when send() raises an exception in process_network_queue (case 3 - all recipients).
    """
    net_queue = queue.Queue()  # Start with an empty queue.
    clock = {"value": 0}
    fake_log_file = io.StringIO()
    fake_sock = FakeSocket(raise_on_send=True)
    other_recipients = ["b", "c"]

    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda duration: real_sleep(0.01))
    monkeypatch.setattr(time, "strftime", lambda fmt, t: "2025-03-03 12:00:00")
    # Force the sending branch (rand_val == 3).
    monkeypatch.setattr(random, "randint", lambda a, b: 3)

    t = threading.Thread(
        target=process_network_queue,
        args=(net_queue, 10, clock, fake_log_file, fake_sock, other_recipients),
        daemon=True
    )
    t.start()
    real_sleep(0.05)
    
    # Check error was logged
    captured = capsys.readouterr().out
    assert "Error sending message to" in captured

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

# --- Tests for main function ---

def test_main_function_with_args(monkeypatch, capsys):
    """
    Test the main function with command line arguments by patching input, socket, and threading.
    """
    fake_sock = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: fake_sock)
    
    # Mock input to return predetermined values
    input_values = iter(["localhost", "12345"])
    monkeypatch.setattr('builtins.input', lambda prompt: next(input_values))
    
    # Create a mock Thread that just records its arguments
    thread_args = []
    
    class MockThread:
        def __init__(self, target, args=(), daemon=False):
            self.target = target
            self.args = args
            self.daemon = daemon
            thread_args.append(args)
        
        def start(self):
            pass
            
        def join(self):
            pass
    
    monkeypatch.setattr(threading, "Thread", MockThread)
    
    # Patch os._exit and sys.argv
    def fake_exit(code):
        pass
    monkeypatch.setattr(os, "_exit", fake_exit)
    monkeypatch.setattr(sys, "argv", ["client.py", "x", "y", "z"])
    
    # Mock out time.sleep to make the test run faster
    monkeypatch.setattr(time, "sleep", lambda s: None)
    
    # Import and run the main function from client.py
    import client
    # We need to wrap this in try-except because our mocked Thread doesn't actually run the target
    try:
        client._test_main = lambda: None  # This won't be called but prevents an error
        if hasattr(client, "__name__"):
            old_name = client.__name__
            client.__name__ = "__main__"
            try:
                exec(open(client.__file__).read(), client.__dict__)
            finally:
                client.__name__ = old_name
    except Exception as e:
        pass
    
    # Check that threads were created for each username
    expected_usernames = ["x", "y", "z"]
    assert len(thread_args) >= len(expected_usernames), "Expected threads for each username"
    
    # Check that each thread received the correct username
    for i, args in enumerate(thread_args[:len(expected_usernames)]):
        assert args[0] == expected_usernames[i], f"Expected thread {i} to have username {expected_usernames[i]}"
        
    # Verify that the arguments passed to simulate_client are correct
    # Format should be: username, host, port, simulation_duration
    for args in thread_args[:len(expected_usernames)]:
        assert len(args) == 4, "Expected 4 arguments to simulate_client"
        assert args[1] == "localhost", f"Expected host to be 'localhost', got {args[1]}"
        assert args[2] == 12345, f"Expected port to be 12345, got {args[2]}"
        assert args[3] == 30, f"Expected simulation_duration to be 30, got {args[3]}"

def test_main_function_without_args(monkeypatch, capsys):
    """
    Test the main function without command line arguments, using default usernames.
    """
    fake_sock = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: fake_sock)
    
    # Mock input to return predetermined values
    input_values = iter(["localhost", "12345"])
    monkeypatch.setattr('builtins.input', lambda prompt: next(input_values))
    
    # Create a mock Thread that just records its arguments
    thread_args = []
    
    class MockThread:
        def __init__(self, target, args=(), daemon=False):
            self.target = target
            self.args = args
            self.daemon = daemon
            thread_args.append(args)
        
        def start(self):
            pass
            
        def join(self):
            pass
    
    monkeypatch.setattr(threading, "Thread", MockThread)
    
    # Patch os._exit and sys.argv - use just script name to trigger default usernames
    def fake_exit(code):
        pass
    monkeypatch.setattr(os, "_exit", fake_exit)
    monkeypatch.setattr(sys, "argv", ["client.py"])
    
    # Mock out time.sleep to make the test run faster
    monkeypatch.setattr(time, "sleep", lambda s: None)
    
    # Import and run the main function from client.py
    import client
    # We need to wrap this in try-except because our mocked Thread doesn't actually run the target
    try:
        client._test_main = lambda: None  # This won't be called but prevents an error
        if hasattr(client, "__name__"):
            old_name = client.__name__
            client.__name__ = "__main__"
            try:
                exec(open(client.__file__).read(), client.__dict__)
            finally:
                client.__name__ = old_name
    except Exception as e:
        pass
    
    # Check that threads were created for default usernames
    expected_usernames = ["a", "b", "c"]
    assert len(thread_args) >= len(expected_usernames), "Expected threads for default usernames"
    
    # Check that each thread received the correct username
    for i, args in enumerate(thread_args[:len(expected_usernames)]):
        assert args[0] == expected_usernames[i], f"Expected thread {i} to have username {expected_usernames[i]}"
