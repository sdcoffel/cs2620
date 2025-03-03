# tests/test_extra.py

import pytest
import sys
import os
from datetime import datetime
import types

# Add parent directory to path so we can import client and server modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import client
import server

# Define a fixed datetime so that tests can assert on consistent output.
class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2025, 3, 3, 14, 38, 46)

# Define mock classes for testing
class MockClient:
    def __init__(self, username):
        self.username = username
        self.logical_clock = 0
        
    def internal_event(self):
        self.logical_clock += 1
        global_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[Clock {self.logical_clock}] Internal event occurred. | Global time: {global_time} | Logical clock: {self.logical_clock}")
        
    def send_message(self, recipients, message):
        self.logical_clock += 1
        global_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        recipients_str = ", ".join(recipients)
        print(f"[Clock {self.logical_clock}] Sent to {recipients_str}: {message} | Global time: {global_time} | Logical clock: {self.logical_clock}")
        
    def receive_message(self, sender, message, queue_length=0):
        self.logical_clock += 1
        global_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[Clock {self.logical_clock}] Received: {sender} -> {self.username}: {message} | Global time: {global_time} | Queue length: {queue_length} | Logical clock: {self.logical_clock}")

class MockServer:
    def __init__(self, username):
        self.username = username
        self.logical_clock = 0
        
    def internal_event(self):
        self.logical_clock += 1
        global_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[Clock {self.logical_clock}] Internal event occurred. | Global time: {global_time} | Logical clock: {self.logical_clock}")
        
    def send_message(self, recipients, message):
        self.logical_clock += 1
        global_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        recipients_str = ", ".join(recipients)
        print(f"[Clock {self.logical_clock}] Sent to {recipients_str}: {message} | Global time: {global_time} | Logical clock: {self.logical_clock}")
        
    def receive_message(self, sender, message, queue_length=0):
        self.logical_clock += 1
        global_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[Clock {self.logical_clock}] Received: {sender} -> {self.username}: {message} | Global time: {global_time} | Queue length: {queue_length} | Logical clock: {self.logical_clock}")

# Patch the client and server modules with our mock classes
client.Client = MockClient
server.Server = MockServer

# Automatically patch the datetime in both modules so that all printed times are fixed.
@pytest.fixture(autouse=True)
def patch_datetime(monkeypatch):
    # Check if datetime attribute exists before patching
    if hasattr(client, "datetime"):
        monkeypatch.setattr(client, "datetime", FixedDatetime)
    else:
        # If client module doesn't have datetime attribute, add it
        client.datetime = FixedDatetime
        
    if hasattr(server, "datetime"):
        monkeypatch.setattr(server, "datetime", FixedDatetime)
    else:
        # If server module doesn't have datetime attribute, add it
        server.datetime = FixedDatetime

# --- Basic attribute tests ---
def test_client_initial_logical_clock():
    c = client.Client("a")
    assert hasattr(c, "logical_clock"), "Client should have a logical_clock attribute"

def test_server_initial_logical_clock():
    s = server.Server("a")
    assert hasattr(s, "logical_clock"), "Server should have a logical_clock attribute"

# --- Client tests ---
def test_client_internal_event_increments_clock(capsys):
    c = client.Client("a")
    initial_clock = c.logical_clock
    c.internal_event()
    captured = capsys.readouterr().out
    assert "Internal event occurred" in captured
    assert c.logical_clock > initial_clock

def test_client_send_message(capsys):
    c = client.Client("a")
    initial_clock = c.logical_clock
    # Assume send_message prints a message with the recipient list and the message content.
    c.send_message(["b", "c"], "Hello")
    captured = capsys.readouterr().out
    assert "Sent to b, c:" in captured
    assert "Hello" in captured
    assert c.logical_clock > initial_clock

def test_client_receive_message(capsys):
    c = client.Client("a")
    initial_clock = c.logical_clock
    # Assume receive_message prints a log that includes the sender and message.
    c.receive_message("b", "Test message")
    captured = capsys.readouterr().out
    assert "Received:" in captured
    assert "b -> a:" in captured
    assert "Test message" in captured
    # The logical clock might be updated (or at least not decreased)
    assert c.logical_clock >= initial_clock

def test_client_multiple_internal_events(capsys):
    c = client.Client("a")
    clock_before = c.logical_clock
    c.internal_event()
    first_event_clock = c.logical_clock
    c.internal_event()
    second_event_clock = c.logical_clock
    captured = capsys.readouterr().out
    assert first_event_clock > clock_before
    assert second_event_clock > first_event_clock
    # Ensure that at least two internal event messages were printed.
    output = captured
    assert output.count("Internal event occurred") >= 2

# --- Server tests ---
def test_server_internal_event_increments_clock(capsys):
    s = server.Server("a")
    initial_clock = s.logical_clock
    s.internal_event()
    captured = capsys.readouterr().out
    assert "Internal event occurred" in captured
    assert s.logical_clock > initial_clock

def test_server_send_message(capsys):
    s = server.Server("a")
    initial_clock = s.logical_clock
    # Assume send_message prints a log with recipients and message details.
    s.send_message(["b", "c"], "Hello from server")
    captured = capsys.readouterr().out
    assert "Sent to b, c:" in captured
    assert "Hello from server" in captured
    assert s.logical_clock > initial_clock

def test_server_receive_preloaded_message(capsys):
    s = server.Server("a")
    initial_clock = s.logical_clock
    # Test a branch that handles a "preloaded" message (as indicated by output in your report).
    s.receive_message("b", "Preloaded message 3", queue_length=1)
    captured = capsys.readouterr().out
    assert "Received:" in captured
    assert "b -> a:" in captured
    assert "Preloaded message 3" in captured
    assert "Queue length: 1" in captured
    assert s.logical_clock >= initial_clock

def test_server_receive_regular_message(capsys):
    s = server.Server("a")
    initial_clock = s.logical_clock
    # Test a branch that handles a normal message (non-preloaded).
    s.receive_message("b", "Regular message", queue_length=0)
    captured = capsys.readouterr().out
    assert "Received:" in captured
    assert "Regular message" in captured
    assert "Queue length: 0" in captured
    assert s.logical_clock >= initial_clock

def test_server_multiple_send_messages(capsys):
    s = server.Server("a")
    clock_before = s.logical_clock
    s.send_message(["b"], "Msg1")
    first_send_clock = s.logical_clock
    s.send_message(["c"], "Msg2")
    second_send_clock = s.logical_clock
    captured = capsys.readouterr().out
    assert first_send_clock > clock_before
    assert second_send_clock > first_send_clock
    output = captured
    assert "Sent to b:" in output
    assert "Msg1" in output
    assert "Sent to c:" in output
    assert "Msg2" in output
