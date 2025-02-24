# Our gRPC API Documentation

The API provides a set of remote procedure calls (RPCs) to support a full-featured messaging application. The service allows users to log in or register, send and receive messages (both in real-time and as pending messages), delete messages, and manage accounts. This documentation outlines each RPC method, the request/response message formats, and usage considerations.

---

## Overview

**Package:** `chat`

All RPC methods are defined under the `ChatService`. The following operations are available:

- **Login:** Handle user authentication and account creation.
- **SendMessage:** Send a message from one user to another.
- **ReceiveMessages:** Stream incoming messages in real-time.
- **GetPendingMessages:** Retrieve the most recent pending messages.
- **MoreMessages:** Retrieve additional pending messages in chunks.
- **DeleteMessage:** Delete a specific message.
- **DeleteAccount:** Delete a user account.
- **ListAccounts:** List all registered accounts, optionally filtered by a wildcard.

---

## RPC Methods

### 1. Login

**Purpose:**  
Authenticate an existing user or create a new account.

**RPC Definition:**

```proto
rpc Login (LoginRequest) returns (LoginResponse);
```

**Request Message: `LoginRequest`**

- **username** (`string`): The user’s unique identifier.
- **password** (`string`): The user's password.
- **is_new** (`bool`): Set to `true` to create a new account; set to `false` to log in to an existing account.

**Response Message: `LoginResponse`**

- **success** (`bool`): Indicates whether the login or account creation was successful.
- **message** (`string`): Provides additional information (e.g., error details or confirmation).

---

### 2. SendMessage

**Purpose:**  
Send a message from one user to another.

**RPC Definition:**

```proto
rpc SendMessage (MessageRequest) returns (MessageResponse);
```

**Request Message: `MessageRequest`**

- **sender** (`string`): Username of the sender.
- **recipient** (`string`): Username of the recipient.
- **message** (`string`): The content of the message.

**Response Message: `MessageResponse`**

- **delivered** (`bool`): Indicates whether the message was successfully delivered.
- **message** (`string`): Additional status or error information.

> **Note:**  
> There is a duplicate set of definitions named `SendMessageRequest` and `SendMessageResponse` later in the file. Currently, the `SendMessage` RPC is defined to use `MessageRequest` and `MessageResponse`. Consider reviewing these duplicates for consistency or deprecation.

---

### 3. ReceiveMessages

**Purpose:**  
Establish a streaming connection for real-time delivery of chat messages.

**RPC Definition:**

```proto
rpc ReceiveMessages (ReceiveMessagesRequest) returns (stream ChatMessageResponse);
```

**Request Message: `ReceiveMessagesRequest`**

- **username** (`string`): The username for which to receive messages.

**Response Stream Message: `ChatMessageResponse`**

- **sender** (`string`): Username of the sender.
- **message** (`string`): The content of the incoming message.

---

### 4. GetPendingMessages

**Purpose:**  
Retrieve the most recent pending messages for a user.

**RPC Definition:**

```proto
rpc GetPendingMessages (PendingMessagesRequest) returns (PendingMessagesResponse);
```

**Request Message: `PendingMessagesRequest`**

- **username** (`string`): The username whose pending messages are requested.

**Response Message: `PendingMessagesResponse`**

- **messages** (`repeated PendingMessage`): A list of pending messages. Each message includes:
  - **sender** (`string`): Sender of the message.
  - **message** (`string`): The content of the message.
- **message** (`string`): A server-provided note or status message.

---

### 5. MoreMessages

**Purpose:**  
Retrieve additional pending messages in batches (chunks of 10).

**RPC Definition:**

```proto
rpc MoreMessages (MoreMessagesRequest) returns (MoreMessagesResponse);
```

**Request Message: `MoreMessagesRequest`**

- **username** (`string`): The username for which additional messages are requested.

**Response Message: `MoreMessagesResponse`**

- **messages** (`repeated PendingMessage`): A list of additional pending messages.
- **message** (`string`): Additional status or information.

---

### 6. DeleteMessage

**Purpose:**  
Delete a specific message based on its content.

**RPC Definition:**

```proto
rpc DeleteMessage (DeleteMessageRequest) returns (DeleteMessageResponse);
```

**Request Message: `DeleteMessageRequest`**

- **message_content** (`string`): The content of the message to be deleted.

**Response Message: `DeleteMessageResponse`**

- **success** (`bool`): Indicates whether the deletion was successful.
- **message** (`string`): Provides further details or error information.

---

### 7. DeleteAccount

**Purpose:**  
Delete a user account. If there are unread messages, the client should confirm deletion.

**RPC Definition:**

```proto
rpc DeleteAccount (DeleteAccountRequest) returns (DeleteAccountResponse);
```

**Request Message: `DeleteAccountRequest`**

- **username** (`string`): The username of the account to be deleted.
- **confirm** (`bool`): Set to `true` to confirm deletion, particularly if there are pending/unread messages.

**Response Message: `DeleteAccountResponse`**

- **success** (`bool`): Indicates if the account deletion was successful.
- **message** (`string`): Additional context or error information.

---

### 8. ListAccounts

**Purpose:**  
Retrieve a list of all registered accounts. An optional filter (wildcard) can be applied to narrow down the results.

**RPC Definition:**

```proto
rpc ListAccounts (ListAccountsRequest) returns (ListAccountsResponse);
```

**Request Message: `ListAccountsRequest`**

- **filter** (`string`): An optional filter. If left empty, all accounts will be returned.

**Response Message: `ListAccountsResponse`**

- **accounts** (`repeated string`): A list of account usernames.
- **message** (`string`): Additional server-provided information.

---

## Usage Considerations

- **Authentication:** Use the `Login` RPC as the entry point for user sessions. Always secure transmission of sensitive data like passwords.

- **Real-time Messaging:** The `ReceiveMessages` RPC provides a stream of incoming messages. Ensure your client can handle streaming responses efficiently.

- **Handling Pending Messages:** The combination of `GetPendingMessages` and `MoreMessages` allows clients to load messages in manageable chunks. Use these methods to implement pagination and improve UI responsiveness.

- **Error and Status Reporting:** Each response includes a `message` field that can be used to relay status updates or error details to the client. Make sure to parse and display these appropriately.

- **Account and Message Management:** Deletion operations (`DeleteMessage` and `DeleteAccount`) are irreversible and should be confirmed by the user—especially account deletion, which requires a confirmation flag if there are unread messages.

- **Filtering Accounts:** The `ListAccounts` RPC supports filtering. If no filter is provided, all registered accounts are returned.
