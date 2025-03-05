# Distributed System Clock Synchronization Simulation

This project simulates a distributed system with logical clocks to demonstrate clock synchronization challenges in distributed environments. It implements a system with multiple clients that communicate through a central server, each with their own logical clock running at different rates.

## Overview

The simulation consists of:

- A central server that routes messages between clients
- Multiple clients (by default named a, b, c) that run at different clock speeds
- Logical clock implementation based on Lamport's logical clock algorithm
- Event logging for analysis

## Test Coverage Report

The project has been extensively tested with 12 test cases across multiple test files, achieving an overall coverage of 92%.

### Coverage Summary

| Module | Statements | Missing | Coverage |
|--------|------------|---------|----------|
| client.py | 110 | 24 | 78% |
| server.py | 68 | 6 | 91% |
| **TOTAL (all files)** | 403 | 33 | 92% |

### Uncovered Code Analysis

Despite good test coverage, certain sections of code remain difficult to test due to their nature:

#### Client.py (Specific uncovered lines: 60, 122-123, 138-139, 148-149, 240-267)

These uncovered lines involve:
1. Network queue data handling (line 60)
2. Exception handlers for network failures (lines 122-123, 138-139, 148-149)
3. Command-line argument processing (lines 240-245)
4. Interactive user input for host and port (lines 247-248)
5. Thread creation and thread joining (lines 254-266)

**Testing challenges:**
- Network queue handling depends on socket communication format
- Exception handlers only execute when network failures occur
- Difficult to simulate specific socket errors in a controlled test environment
- Requires simulating user input and command-line arguments
- Uses multi-threading with join operations that are difficult to mock
- Contains system-level interaction logic

#### Server.py (Specific uncovered lines: 80, 111-112, 140-142, 186)

These areas are difficult to cover:
1. Exception handling for empty queue (line 80)
2. Connection handling for empty username (lines 111-112)
3. Exception handling in client connection (lines 140-142)
4. Main function entry point (line 186)

**Testing challenges:**
- Empty queue exception rarely triggered in normal test execution
- Empty username edge case not triggered in normal tests
- Exception handling requires simulating network failures
- Entry point is not called during test execution which initializes server differently

### Testing Approach

The project includes dedicated test files that cover the main functionality:
- `test_client.py` tests the client functionality with 99% coverage
- `test_server.py` tests the server functionality with 98% coverage

These tests focus on the primary logic and mechanisms of the distributed system, while some edge cases and system-level interactions remain difficult to test without adding code specifically for testing purposes.

## Technical Implementation

### Server (server.py)

The server acts as a message router between clients. It maintains a connection with each client and handles message delivery between them.

**Key Components:**

- `active_clients`: Dictionary that maps usernames to their connection and message queue
- `SendMessage()`: Puts messages in the recipient's queue
- `ReceiveMessages()`: Thread function that sends queued messages to a client
- `handle_client()`: Manages each client connection in its own thread
- `start_server()`: Initializes the server socket and accepts connections

**Implementation Details:**

- Uses TCP sockets (`socket.AF_INET, socket.SOCK_STREAM`) for reliable communication
- Threaded architecture with a dedicated thread per client
- Unique message queues (`queue.Queue()`) for each connected client
- Message format: `recipient::message` for routing messages
- Error handling for disconnections and malformed messages

### Client (client.py)

Each client simulates a node in the distributed system with its own logical clock.

**Key Components:**

- `receive_messages()`: Thread function that listens for messages from the server
- `process_network_queue()`: Main logic for processing clock ticks and events
- `simulate_client()`: Sets up and runs the client simulation
- Clock rate: Random integer between 1-6 ticks per second
- Logical clock: Simple counter that increments based on events

**Implementation Details:**

- Logical Clock: Implemented as a simple counter that increments on each event
- Network Queue: Uses Python's `queue.Queue()` to buffer incoming messages
- Clock Synchronization: Updates logical clock when receiving messages
- Event Types:
  - Internal events (70% probability)
  - Send message to one client (10% probability)
  - Send message to another client (10% probability)
  - Send message to all clients (10% probability)
- Threading: Two threads per client for receiving and processing messages

**Clock Update Rules:**

1. Increment clock by 1 for each internal event
2. When sending a message, include current logical clock time
3. When receiving a message, set clock to max(local_clock, received_clock) + 1

## Code Breakdown

### server.py

```python
# Key data structures
active_clients = {}  # Maps usernames to {conn: socket, queue: Queue()}

# Core functionality
def SendMessage(sender, recipient, message):
    # Places message in recipient's queue

def ReceiveMessages(username):
    # Thread function that sends queued messages to the client

def handle_client(conn, addr):
    # Thread function that handles each client connection
    # 1. Receives username
    # 2. Adds client to active_clients
    # 3. Starts ReceiveMessages thread
    # 4. Processes messages from client

def start_server():
    # Sets up server socket and accepts connections
    # Runs handle_client in a new thread for each connection
```

### client.py

```python
# Core functionality
def receive_messages(sock, net_queue):
    # Thread function that receives messages from server and adds to queue

def process_network_queue(net_queue, clock_rate, clock, log_file, sock, other_recipients):
    # Main logic for handling events on each clock tick:
    # 1. Increment logical clock
    # 2. If messages in queue, process one message
    # 3. Otherwise, generate random event:
    #    - Internal event (70% chance)
    #    - Send message to other client(s) (30% chance)

def simulate_client(username, host, port, simulation_duration):
    # Set up client:
    # 1. Connect to server
    # 2. Assign random clock rate (1-6 ticks/sec)
    # 3. Initialize logical clock
    # 4. Start threads for receiving and processing
    # 5. Run for simulation_duration seconds
```

## How It Works

1. **Server Initialization**:

   - Server starts and listens on port 50051
   - Waits for client connections

2. **Client Connection**:

   - Each client connects to the server
   - Sends username as the first message
   - Server adds client to active_clients dictionary
   - Server starts a thread to handle messages for this client

3. **Simulation Cycle**:

   - Each client has a random clock rate (1-6 ticks per second)
   - On each clock tick:
     - Increment logical clock
     - If messages in queue, process one and update clock
     - If no messages, generate a random event (internal or send message)
   - All events are logged with logical clock value and global time

4. **Message Routing**:

   - Client sends: `recipient::message`
   - Server places in recipient's queue
   - Recipient processes message on its next clock tick

5. **Clock Synchronization**:
   - Messages include sender's logical clock value
   - Recipient updates its clock to max(local, received) + 1

## Running the Simulation

### Start the Server

```bash
python server.py
```

The server will start listening on port 50051 by default.

### Start the Clients

```bash
python client.py a b c
```

You'll be prompted to enter:

- Server host (localhost or IP address)
- Server port (50051 by default)

The simulation will run for 30 seconds by default and generate log files for each client.

## Log Files

Each client generates a log file (log_a.txt, log_b.txt, log_c.txt) containing:

- Logical clock values
- Global timestamps
- Queue lengths
- Event descriptions (message received, message sent, internal event)

**Sample Log Entry:**

```
[Clock 6] Sent to b, c: Logical clock time: 5 | Global time: 2025-02-27 19:56:13 | Logical clock: 6
```

## Usefulness

We intend for the simulation to show:

1. **Clock Drift**: Observe how different clock rates lead to divergence
2. **Message Ordering**: Analyze causality and happens-before relationships
3. **Queue Buildup**: See how slower clients may develop message backlogs
4. **Synchronization Effectiveness**: Evaluate how well Lamport clocks maintain event ordering

Uses:

- Understanding logical clock synchronization in distributed systems
- Observing how different clock rates affect message ordering
- Studying causality and partial ordering in distributed systems
- Visualizing message propagation delays and their effects
