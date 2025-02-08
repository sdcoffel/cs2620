# Documentation for Savanna + Ian's Messaging App

## Security

We have worked to make the application as secure as is reasonably possible, but we need to make note of some critical weaknesses:

- Passwords are hashed before they are stored/persisted, so cleartext passwords are _never_ stored. However, we are reliant on the security of the network in transmitting passwords or hashed passwords from client to server. So, if a communication between client and server containing a password or hashed password is intercepted, it can be used for unauthorized access/forged communications. In short, passwords are secure at rest by design, but for security in transit we critically assume the security of the network.
