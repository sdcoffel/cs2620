import uuid
from datetime import datetime

# In-memory store of messages (lowercase)
messages = {}


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


def create_message(sender, receiver, content):
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


def delete_message(message_uuid):
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


def list_messages():
    """
    List all messages currently stored in the messages dict.

    Returns:
        list: A list of all message objects.
    """
    return list(messages.values())
