# Documentation for Savanna + Ian's Messaging App

## Installation

This system is built to run on Python 3.13.2. There are no package requirements beyond the packages that ship with all Python installations.

## Running the Server

From this directory, run `python server.py` and the server will boot. The server runs on port `12345`. Note that if you do not run the server first, you will encounter a socket error and will not be able to connect. Always run the server before firing up the GUI.

## Running the Client GUI

From this directory, run `python GUI.py` and the GUI application will load. Again, the server runs on port `12345` so input that port as well as the IP address of the computer running the server into the client to connect. If the client and the server are on the same computer, you can use `localhost` to connect. Note that eduroam and harvard secure are a bit too encrypted to just send anything over the network, so you need to be on 'Harvard University' -- the public wifi, in order to talk across multiple machines. 

## Wire Protocols

In `settings.py` we have a constant named `JSON_MODE`.

Our application supports communication in both our custom wire protocol as well as in JSON. Set `JSON_MODE` to `True` to communicate in JSON. Set `JSON_MODE` to `False` to communicate in our custom wire protocol.

Changing the value of `JSON_MODE` will switch communication for both the client and the server. In our implementation, both must communicate in the same wire protocol --- i.e., you cannot have the server communicate in JSON and the client communicate in the custom wire protocol or vice versa.

For more information about our specifc custom wire protocol, see the engineering notebook files. 

### Versioning

Our current implementation uses version `v0` of our wire protocol. Any future change to the wire protocol will require a new version identifier be implemented and screened for.

## Design Notes

Note that we do not consider the deletion of pending messages, as it wasn't part of the specification. Because only the reciever can delete messages, we do not need to worry about adding functionality to deleting pending messages. Once the reciever reads the pending messages, they are stored on the server and the reciever can no longer interact with them.

### Persistent Storage

Our server code is able to persist data to disk using our custom storage format which gets encoded in `txt` files. Do not delete the `txt` files if you want to retain data. Do not delete `txt` files while the server is running.

Future changes to the persistent storage format will require a new version identifier be implemented and screened for. We call this implementation version `v0`.

### Limitations and Notes

Some important limitations:

- Usernames and passwords are case sensitive.

- Clients can delete however many messages they want, and once they are deleted, they are lost forever to the client (satisfying the point on the rubric that clients cannot recover deleted messages.) However, the server keeps a log of every message ever sent across the service for our own debugging purposes. Again, this is not accessbile to the client, so this is not an issue, but we wanted to clear this up for the graders in case they get confused.

See also the notes below on security.

## Code Organization

We have divided our code into the following files with the following purposes:

- `accounts.py` - manages account data, including persisting to disk.
- `messages.py` - manages messages data, including persisting to disk.
- `server.py` - handles communication and application logic for the server.
- `client.py` - handles communication and application logic for the client.
- `gui.py` - implements the graphical user inferface.
- `settings.py` - see "Wire Protocols" above.

Test code organization is covered below.

Within each of these code files our code is organized into classes and methods. Docstrings document the purpose, interface, and behavior of each.

## Test Suite

Make sure you change your directory into the `unit_tests` folder that way paths work properly before running any unit tests.

We have comprehensive unit tests that cover all components and methods of our distributed system. You can run any of our test suites with:

- `python test_accounts.py` - tests the accounts data managers.
- `python test_messages.py` - tests the messages data managers.
- `python test_server.py` - tests the code for the server logic and connectivity.
- `python test_client.py` - tests the code for the client logic and connectivity.
- `python test_gui.py` - tests the GUI implementation.

## Security

We have worked to make the application as secure as is reasonably possible, but we need to make note of some critical weaknesses:

- Passwords are hashed before they are stored/persisted, so cleartext passwords are _never_ stored. However, we are reliant on the security of the network in transmitting hashed passwords from client to server. So, if a communication between client and server containing a hashed password is intercepted, it can be used for unauthorized access/forged communications. In short, passwords are secure at rest by design, but for security in transit we critically assume the security of the network. (Using a simple hash for transmitting passwords was approved by the course staff on Ed.)


## Wire Protocol Comparison: JSON vs our custom protocol

Full documentation of the comparison is covered across the engineering notebooks in the engineering notebooks folder. Unsurprisingly, our protocol is more compact than JSON; we send fewer bytes over the network on every send/recieve call over the network. 