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


def delete_message(content, file_path):
    """
    Delete a message by its content from the file.

    Args:
        content (str): The content of the message to delete.
        file_path (str): The path to the file where messages are stored.

    Returns:
        bool: True if the message was found and deleted, False otherwise.
    """
    messages = []
    message_found = False

    # Read all messages from the file
    try:
        with open(file_path, 'r') as file:
            for line in file:
                parts = line.strip().split('|')
                if len(parts) == 5:
                    message_id, datetime, sender, receiver, message_content = parts
                    if message_content != content:
                        messages.append(line)
                    else:
                        message_found = True
    except FileNotFoundError:
        return False

    # Write the remaining messages back to the file
    with open(file_path, 'w') as file:
        for message in messages:
            file.write(message)

    return message_found


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



def save_pending_messages(file_path, recipient, sender, message):
    """Append a single pending message to the file each time."""
    with open(file_path, 'a') as file:
        line = f"{recipient}|{sender}|{message}\n"
        file.write(line)



def load_pending_messages(file_path):
    """Load pending messages from a file."""
    pending_messages = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                parts = line.strip().split('|')
                if len(parts) == 3:
                    recipient, sender, message = parts
                    if recipient not in pending_messages:
                        pending_messages[recipient] = []
                    pending_messages[recipient].append((sender, message))
    except FileNotFoundError:
        pass
    return pending_messages



def delete_pending_messages(file_path, recipient):
    """Delete all pending messages for a recipient from the file."""
    pending_messages = load_pending_messages(file_path)
    if recipient in pending_messages:
        del pending_messages[recipient]
        with open(file_path, 'w') as file:
            for rec, messages in pending_messages.items():
                for sender, message in messages:
                    line = f"{rec}|{sender}|{message}\n"
                    file.write(line)



# if __name__ == '__main__': 
    # # Test save_pending_messages and load_pending_messages
    # test_file_path = "test_pending_messages.txt"
    
    # # Create some test pending messages
    # test_pending_messages = {
    #     "user1": [("user2", "Hello user1!"), ("user3", "Hi user1!")],
    #     "user2": [("user1", "Hello user2!")]
    # }
    
    # # Save the test pending messages to the file
    # save_pending_messages(test_file_path, test_pending_messages)
    
    # # Load the pending messages from the file
    # loaded_pending_messages = load_pending_messages(test_file_path)
    