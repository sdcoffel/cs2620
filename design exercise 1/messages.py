import uuid
from datetime import datetime


def is_valid_message(message):
    """
    Check if the given message dictionary is valid.
    A valid message has the keys:
        - 'uuid'
        - 'datetime'
        - 'sender'
        - 'receiver'
        - 'content'
    """
    required_keys = {"uuid", "datetime", "sender", "receiver", "content"}
    if not isinstance(message, dict):
        return False
    return set(message.keys()) == required_keys


def create_message(sender, receiver, content, messages):
    """
    Create a new message and store it in the in-memory messages dict.

    Args:
        sender (str): The identifier (e.g., username) of the sender.
        receiver (str): The identifier of the receiver.
        content (str): The content of the message.

    Returns:
        dict: The newly created message object.

    Raises:
        ValueError: If the message object is invalid.
    """
    new_uuid = str(uuid.uuid4())
    # Capture the current time upon message creation
    timestamp = datetime.now().isoformat()

    message_object = {
        "uuid": new_uuid,
        "datetime": timestamp,
        "sender": sender,
        "receiver": receiver,
        "content": content,
    }

    # Validate the message object
    if not is_valid_message(message_object):
        raise ValueError("Invalid message object structure.")

    # Store the message
    messages[new_uuid] = message_object
    return message_object


def delete_message(message_uuid, messages):
    """
    Delete a message by UUID from the messages dict.

    Args:
        message_uuid (str): The UUID of the message to delete.

    Returns:
        bool: True if the message was found and deleted, False otherwise.
    """
    if message_uuid in messages:
        del messages[message_uuid]
        return True
    return False


def list_messages(messages, sender = None, receiver= None):
    """
    List all messages currently stored in the messages dict.
    If sender and receiver are specified, list messages between them.

    Args:
        sender (str): The identifier of the sender.
        receiver (str): The identifier of the receiver.

    Returns:
        list: A list of message objects.
    """
    if sender and receiver:
        filtered_messages = [
            msg for msg in messages.values()
            if (msg['sender'] == sender and msg['receiver'] == receiver) or
               (msg['sender'] == receiver and msg['receiver'] == sender)
        ]
        # Sort messages by datetime
        filtered_messages.sort(key=lambda x: x['datetime'])
        return filtered_messages
    else:
        # Return all messages sorted by datetime
        all_messages = list(messages.values())
        all_messages.sort(key=lambda x: x['datetime'])
        return all_messages


def format_datetime(dt_str):
    """
    Format the datetime string to a more readable format, truncating to the nearest hour and minute.

    Args:
        dt_str (str): The datetime string in ISO format.

    Returns:
        str: The formatted datetime string.
    """
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%Y-%m-%d %H:%M")


def load_messages(file_path):
    """Load messages from a file. These would have previously been serialized and written to disk"""
    messages = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                parts = line.strip().split(',')
                if len(parts) == 5:
                    message_id, datetime, sender, receiver, content = parts
                    messages[message_id] = {
                        "uuid": message_id,
                        "datetime": datetime,
                        "sender": sender,
                        "receiver": receiver,
                        "content": content
                    }
    except FileNotFoundError:
        pass
    return messages



def save_messages(file_path, messages):
    """Save messages to a file. Serialize the messages and write them to disk"""
    with open(file_path, 'w') as file:
        for message in messages.values():
            line = f"{message['uuid']}|{message['datetime']}|{message['sender']}|{message['receiver']}|{message['content']}\n"
            file.write(line)





# if __name__ == '__main__': 
#     # In-memory store of messages (lowercase)
#     messages = {}

#     # Create a new message
#     new_message = create_message("Alice", "Bob", "Hello, Bob!")
#     message2 = create_message("Bob", "Alice", "Hello, Alice!")
#     message3 = create_message("Alice", "Bob", "How are you?")
#     message4 = create_message("Bob", "Alice", "I'm good, thanks!")
#     message5 = create_message("Alice", "Bob", "That's great to hear!")
#     message6= create_message("Bob", "Alice", "I'll talk to you later.")

#     # List all messages between Alice and Bob

#     all_messages = list_messages()
#     print("\nAll messages:")
#     for msg in all_messages:
#         print(f"{format_datetime(msg['datetime'])} - {msg['sender']} to {msg['receiver']}: {msg['content']}")

#     # Delete a message
#     deleted1 = delete_message(new_message['uuid'])
#     deleted2 = delete_message(message2['uuid'])

#     # List all messages between Alice and Bob
#     all_messages = list_messages()
#     print("\nAll messages after deletion:")
#     for msg in all_messages:
#         print(f"{format_datetime(msg['datetime'])} - {msg['sender']} to {msg['receiver']}: {msg['content']}")   

#     #prints all the messages in a nice format
#     print("\nmessages dictionary:")
#     for msg_id, msg in messages.items():
#         print(f"{msg_id}: {msg}")