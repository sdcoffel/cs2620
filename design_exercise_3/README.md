# Distributed Chat Application

A fault-tolerant, distributed chat application built with gRPC, ZooKeeper, and Python. The system implements the Raft consensus algorithm for leader election and provides reliable messaging between users even when servers go down.

## Table of Contents

- [Project Overview](#project-overview)
- [System Architecture](#system-architecture)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Components](#components)
- [Testing](#testing)
- [Fault Tolerance](#fault-tolerance)

## Project Overview

This distributed chat application provides a reliable messaging platform with the following capabilities:
- User account management (creation, login, deletion)
- Real-time message delivery between online users
- Offline message storage for users not currently connected
- Server-side fault tolerance using the Raft consensus algorithm
- Cluster management with ZooKeeper

The application is designed to maintain message delivery even in the presence of server failures, ensuring high availability and data consistency.

## System Architecture

The system follows a client-server architecture with multiple replicated servers:

1. **Client Layer**: GUI or command-line interface for user interactions
2. **Server Layer**: Multiple server instances that can handle client requests
3. **Consensus Layer**: Raft implementation for leader election and state replication
4. **Storage Layer**: Persistent storage for messages and account information

Servers communicate with each other through gRPC to synchronize state and implement the Raft consensus protocol. ZooKeeper is used for server discovery and configuration management.

## Features

- **Account Management:**
  - Create new user accounts
  - Login with existing accounts
  - Delete accounts (with confirmation for unread messages)
  - List available accounts with optional regex filtering

- **Messaging:**
  - Send messages to online or offline users
  - Retrieve pending messages on login
  - Stream real-time messages for online users
  - Request more pending messages in batches

- **Fault Tolerance:**
  - Server replication for high availability
  - Leader election using Raft consensus
  - Automatic recovery from server failures
  - Persistent storage of messages and account information

## Installation

### Prerequisites

- Python 3.7 or higher
- ZooKeeper (required for server cluster management)
- gRPC and Protocol Buffers

### Setup

1. Install Python dependencies:
```bash
pip install grpcio grpcio-tools kazoo
```

2. Install and start ZooKeeper:
```bash
# The application uses the default ZooKeeper port (2181)
# Start ZooKeeper with the provided configuration
zkServer.sh start zoo.cfg
```

3. Clone the repository:
```bash
git clone <repository-url>
cd design_exercise_3
```

## Usage

### Starting the Server Cluster

Run the server script to start a server cluster with 3 instances (for 2-fault tolerance):

```bash
python server.py
```

This will start three server processes on ports 50051, 50052, and 50053. The first server (server1) is designated as the leader by default.

### Adding Additional Servers

While the server is running, you can add additional server instances:

1. Enter `add` when prompted
2. Provide a server ID (e.g., "server4")
3. Specify a port number (e.g., 50054)

### Starting a Client

Run the client with a GUI:

```bash
python GUI.py
```

Or use the command-line client:

```bash
python client.py
```

### Client Operations

1. **Login/Create Account:**
   - Enter username and password
   - Specify whether it's a new account or existing one

2. **Send Messages:**
   - Set a recipient
   - Type a message and send

3. **View Messages:**
   - Pending messages are shown automatically on login
   - Request more messages as needed

4. **Manage Account:**
   - List other users
   - Delete account (with confirmation for unread messages)

## Components

### Core Files

- **chatserver.py**: Primary server implementation for chat functionality
- **client.py**: Client implementation for interacting with the server
- **GUI.py**: Graphical user interface for the chat application
- **server.py**: Server startup and cluster management
- **raftnode.py**: Implementation of the Raft consensus algorithm

### Supporting Files

- **accounts.py**: Account management functions
- **messages.py**: Message handling and persistence
- **operations.py**: Serialization utilities
- **zookeeper_manager.py**: Interface to ZooKeeper for server discovery
- **config_manager.py**: Configuration management for server settings

### Protocol Files

- **chatapp.proto**: Protocol Buffer definitions
- **chatapp_pb2.py**: Generated Protocol Buffer code
- **chatapp_pb2_grpc.py**: Generated gRPC service code

## Testing

The application includes comprehensive testing:

### Unit Tests

Run unit tests with pytest:

```bash
pytest unit_tests.py -v
```

### Extended Tests

Additional tests to increase code coverage:

```bash
pytest extended_unit_tests.py -v
```

### Server and Client Tests

Tests for server and client components:

```bash
pytest server_client_tests.py -v
```

### Integration Tests

Run integration tests to verify system-wide functionality:

```bash
pytest integration_tests.py -v
```

### Coverage Reports

Generate coverage reports to analyze test coverage:

```bash
pytest --cov=. --cov-report=term unit_tests.py extended_unit_tests.py server_client_tests.py
```

## Fault Tolerance

The application implements several mechanisms for fault tolerance:

### 1. Server Replication

- Default configuration of 3 servers for 2-fault tolerance
- Additional servers can be added during runtime

### 2. Raft Consensus

- Leader election for coordinating server actions
- Heartbeat messages to detect server failures
- Vote-based consensus for leader selection

### 3. Persistent Storage

- Accounts stored in `all_accounts_ever.txt`
- Pending messages stored in `pending_messages.txt`
- Messages are immediately persisted to disk

### 4. ZooKeeper Integration

- Server registration and discovery
- Node monitoring for failure detection
- Configuration management

### Recovery Process

When a server fails:
1. Heartbeat timeouts trigger leader election (if leader failed)
2. Remaining servers establish a new leader
3. Clients can reconnect to any available server
4. Pending messages are preserved and delivered when possible