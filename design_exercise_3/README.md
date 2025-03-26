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
- [Design Decisions](#design-decisions)
- [Performance Considerations](#performance-considerations)
- [Troubleshooting](#troubleshooting)
- [Future Enhancements](#future-enhancements)

## Project Overview

This distributed chat application provides a reliable messaging platform with the following capabilities:

- User account management (creation, login, deletion)
- Real-time message delivery between online users
- Offline message storage for users not currently connected
- Server-side fault tolerance using the Raft consensus algorithm
- Cluster management with ZooKeeper

The application is designed to maintain message delivery even in the presence of server failures, ensuring high availability and data consistency. The system can tolerate up to n-1/2 server failures while still functioning properly, where n is the total number of servers in the cluster.

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
  - Message timestamping for chronological ordering

- **Fault Tolerance:**

  - Server replication for high availability
  - Leader election using Raft consensus
  - Automatic recovery from server failures
  - Persistent storage of messages and account information
  - Seamless client reconnection to available servers

- **System Management:**
  - Dynamic addition of new servers to the cluster
  - Server status monitoring
  - Configuration management through ZooKeeper

## Installation

### Prerequisites

- Python 3.7 or higher
- ZooKeeper (required for server cluster management)
- gRPC and Protocol Buffers

### Setup

1. Install Python dependencies:

   ```bash
   pip install grpcio grpcio-tools kazoo pytest pytest-cov
   ```

2. Install and start ZooKeeper (you can install via pip, homebrew, or whatever your preferred method is, by referring to the ZooKeeper documentation):

   ```bash
   # The application uses the default ZooKeeper port (2181)
   # Start ZooKeeper
   zkServer start
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

You can also use the dedicated script for adding servers:

```bash
python add_new_server.py <server_id> <port>
```

### Verifying Server Status

To check the status of all servers in the cluster:

```bash
python verify_servers.py
```

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
   - Messages include timestamps for chronological ordering

4. **Manage Account:**
   - List other users
   - Delete account (with confirmation for unread messages)
   - Use regex patterns to filter user lists

## Components

### Core Files

- **chatserver.py**: Primary server implementation for chat functionality
- **client.py**: Client implementation for interacting with the server
- **GUI.py**: Graphical user interface for the chat application
- **server.py**: Server startup and cluster management
- **raftnode.py**: Implementation of the Raft consensus algorithm

### Supporting Files

- **accounts.py**: Account management functions and persistence
- **messages.py**: Message handling, queuing, and persistence
- **operations.py**: Serialization utilities and common operations
- **zookeeper_manager.py**: Interface to ZooKeeper for server discovery
- **config_manager.py**: Configuration management for server settings
- **server_management_functions.py**: Functions for managing server instances
- **add_new_server.py**: Script for adding new servers to the cluster
- **verify_servers.py**: Script for verifying server status

### Protocol Files

- **chatapp.proto**: Protocol Buffer definitions for services and messages
- **chatapp_pb2.py**: Generated Protocol Buffer code
- **chatapp_pb2_grpc.py**: Generated gRPC service code

## Testing

The application includes comprehensive testing:

### Running All Tests

To run all tests at once:

```bash
pytest unit_tests.py extended_unit_tests.py integration_tests.py server_client_tests.py -v
```

### Unit Tests

Run unit tests with pytest:

```bash
pytest unit_tests.py -v
```

These tests cover core functionality including account management, message handling, and basic server operations.

### Extended Tests

Additional tests to increase code coverage:

```bash
pytest extended_unit_tests.py -v
```

These tests focus on edge cases and error handling.

### Server and Client Tests

Tests for server and client components:

```bash
pytest server_client_tests.py -v
```

These tests verify the interaction between servers and clients.

### Integration Tests

Run integration tests to verify system-wide functionality:

```bash
pytest integration_tests.py -v
```

Integration tests validate the entire system working together, including fault tolerance and recovery.

### Coverage Reports

Generate coverage reports to analyze test coverage:

```bash
pytest --cov=. --cov-report=term unit_tests.py extended_unit_tests.py server_client_tests.py
```

The project aims for at least 80% test coverage across all components.

## Fault Tolerance

The application implements several mechanisms for fault tolerance:

### 1. Server Replication

- Default configuration of 3 servers for 2-fault tolerance
- Additional servers can be added during runtime
- System can operate with a simple majority of servers (n/2 + 1)

### 2. Raft Consensus

- Leader election for coordinating server actions
- Heartbeat messages to detect server failures
- Vote-based consensus for leader selection
- Term-based leadership to prevent split-brain scenarios

### 3. Persistent Storage

- Accounts stored in `all_accounts_ever.txt`
- Pending messages stored in `pending_messages.txt`
- Messages are immediately persisted to disk
- Log-based persistence for operation history

### 4. ZooKeeper Integration

- Server registration and discovery
- Node monitoring for failure detection
- Configuration management
- Ephemeral znodes for live server tracking

### Recovery Process

When a server fails:

1. Heartbeat timeouts trigger leader election (if leader failed)
2. Remaining servers establish a new leader
3. Clients can reconnect to any available server
4. Pending messages are preserved and delivered when possible
5. Failed servers can rejoin the cluster when restarted

## Design Decisions

### Consistency Model

The system implements a strong consistency model through the Raft consensus algorithm. All operations that modify system state must be processed through the leader server, which then replicates these changes to follower servers. This ensures that all servers have a consistent view of the system state.

### Message Delivery Guarantees

The system provides at-least-once message delivery guarantees. Messages are persisted to disk before being acknowledged to the sender, and are only removed from storage after being successfully delivered to the recipient. In case of server failures, message delivery may be delayed but is never lost.

### Security Considerations

- Passwords are stored with basic encryption (for demonstration purposes only)
- Server-to-server communication is not encrypted in this version
- Client-to-server communication is not encrypted in this version
- For production use, TLS encryption should be implemented

### Additional Critical Insights from Development

Below are key insights and design decisions drawn from our engineering discussions and implementation notes:

1. **Fixed Initial Cluster + Extension**  
   We start with a baseline cluster of three servers, using hardcoded configuration or a simple startup script. After verifying the minimal functionality, we extend the cluster by allowing new servers to join. This approach ensures a reliable foundation (3 replicas) before enabling further scaling.

2. **Adding Servers with Unique IDs and Ports**  
   We do not permit servers to be added with the same server ID or the same port. If a user attempts to add a new server with a conflicting identifier, the system logs an error message and prevents the server from starting. This design choice avoids confusion and conflicts in the Raft cluster, as each server must be uniquely identifiable.

3. **Strict Leader Election**  
   We rely solely on the Raft consensus protocol to designate a leader. We do not allow any server to forcibly take leadership outside of Raft’s election process. If the current leader fails (or is suspected to have failed due to missed heartbeats), a standard Raft election automatically begins, ensuring continuous availability without arbitrary “leader swapping.”

4. **Heartbeat Mechanism**  
   Each server receives regular heartbeats from the leader. If heartbeats are not received in a timely manner, servers trigger Raft’s leader election. This mechanism is crucial for quickly detecting failed or unresponsive leaders and minimizing disruption to the system.

5. **ZooKeeper/Kazoo for Server Registration**  
   We use ZooKeeper to dynamically track servers in the cluster. Each server creates an ephemeral znode upon startup, which is automatically removed if it fails or disconnects. The Kazoo library in Python simplifies our interaction with ZooKeeper, letting us maintain an up-to-date registry of active replicas.

6. **Testing Approach**  
   Our implementation features a robust suite of both unit tests and integration tests. We use mocks to test individual components in isolation (e.g., message handling, account management). Then, we run full integration tests to validate the entire system across multiple servers, testing leader elections, server crashes, user reconnections, and more. Manual testing further confirms that the chat application is resilient in real-world scenarios such as network outages and unexpected server failures.

Overall, these additional design insights highlight how careful handling of leader election, unique server IDs/ports, heartbeat monitoring, and dynamic registration in ZooKeeper all contribute to a cohesive, fault-tolerant distributed chat system.

## Performance Considerations

### Scalability

- The system can scale by adding more server instances
- ZooKeeper provides service discovery for dynamic scaling
- The current implementation is optimized for small to medium deployments

### Optimizations

- Batch processing of messages for efficient network usage
- Lazy loading of messages to reduce memory usage
- Efficient leader election to minimize downtime during failures

## Troubleshooting

### Common Issues

1. **Connection Issues:**

   - Ensure ZooKeeper is running (`zkServer.sh status`)
   - Check that server ports are available and not blocked by firewall
   - Verify network connectivity between clients and servers

2. **Server Failures:**

   - Check logs for error messages
   - Verify ZooKeeper connection
   - Restart failed server instances if necessary

3. **Message Delivery Problems:**
   - Verify recipient exists and is spelled correctly
   - Check sender's connection status
   - Ensure cluster has a leader elected

### Logging

- Server logs are output to console by default
- Set verbose logging for more detailed information

## Future Enhancements

1. **Security Improvements:**

   - Implement TLS encryption for all communications
   - Add proper password hashing and security
   - Implement authentication tokens

2. **Feature Additions:**

   - Group chat functionality
   - Message read receipts
   - File transfer capabilities
   - Rich text messaging

3. **Performance Enhancements:**

   - Message compression
   - Connection pooling
   - Optimized data storage

4. **UI Improvements:**
   - Enhanced GUI with modern design
   - Mobile client support
   - Web interface
