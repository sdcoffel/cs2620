import unittest
from unittest.mock import patch, Mock
import json
import socket
import sys

sys.path.append("../")
from client import Client
from settings import JSON_MODE

class TestChatClient(unittest.TestCase):
    """
    Test suite that tracks:
      - JSON vs. Non-JSON modes
      - Send vs. Receive byte counts
    """

    custom_send_bytes = 0
    custom_receive_bytes = 0
    json_send_bytes = 0
    json_receive_bytes = 0

    def setUp(self):
        """Set up before each test method."""
        self.client = Client()

        #mock socket
        self.mock_socket = Mock(spec=socket.socket)
        self.client.client_socket = self.mock_socket

    def tearDown(self):
        """Clean up after each test method."""
        self.client.close_connection()


    # ----------------------------------------------------------------
    # RECEIVING MESSAGES
    # ----------------------------------------------------------------

    @patch("settings.JSON_MODE", new=True) 
    def test_receive_messages_json_mode(self, *args):
        """
        Test receiving JSON messages. We simulate the socket returning
        a JSON-encoded string and check how many bytes we "received".
        """
        test_message = {"sender": "testuser", "message": "Test message"} #note that these require extra brackets and other info, which we don't have 
        encoded = json.dumps(test_message).encode("utf-8")

      
        self.mock_socket.recv.return_value = encoded
        self.client.receive_messages()

        #add bytes in JSON mode
        self.__class__.json_receive_bytes += len(encoded)

    @patch("settings.JSON_MODE", new=False)
    def test_receive_messages_plain_mode(self, *args):
        """
        Test receiving plain text messages. We simulate the socket returning
        a simple UTF-8–encoded string in "recipient:message" format.
        """

        test_message = "testuser: Test message" #same information as JSON, just much less to encode- note that this could also be WAY smaller if we compressed even more 
        encoded = test_message.encode("utf-8")

        self.mock_socket.recv.return_value = encoded
        self.client.receive_messages()

        #track bytes in non-JSON mode
        self.__class__.custom_receive_bytes += len(encoded)


    # ----------------------------------------------------------------
    # SENDING MESSAGES
    # ----------------------------------------------------------------

    @patch("settings.JSON_MODE", new=True)
    def test_send_messages_json_mode(self, *args):
        """
        Self explanatory.
        """
        recipient = "recipient"
        message = "Test message"
        full_message = f"{recipient}:{message}"  

    
        self.client.send_messages(recipient, message)
        expected_payload = json.dumps({"raw_message": full_message}).encode("utf-8")
        self.__class__.json_send_bytes += len(expected_payload)


    @patch("settings.JSON_MODE", new=False)
    def test_send_messages_plain_mode(self, *args):
        """
        Self explanatory 
        """
        recipient = "recipient"
        message = "Test message"
        full_message = f"{recipient}:{message}"  


        self.client.send_messages(recipient, message)
        expected_payload = full_message.encode("utf-8")
        self.mock_socket.send.assert_called_once_with(expected_payload)

        self.__class__.custom_send_bytes += len(expected_payload)


class CustomTestRunner(unittest.TextTestRunner):
    """
    Yeah yeah same stuff. 
    """
    def run(self, test):
        result = super().run(test)

        print("\n\nTest Summary")
        print("-------------------")
        print(f"{result.testsRun} tests run in total.")
        if not result.wasSuccessful():
            print(f"{len(result.failures) + len(result.errors)} tests failed.")
        else:
            print("All tests passed!")

        print("\nDetailed Byte Size Totals (Application Payload Only):")

        #custom summaries
        print("\nCustom (Plain) Mode:")
        print(f"  Sent:     {TestChatClient.custom_send_bytes} bytes")
        print(f"  Received: {TestChatClient.custom_receive_bytes} bytes")
        print(f"  Total:    {TestChatClient.custom_send_bytes + TestChatClient.custom_receive_bytes} bytes")

        #summaries from json 
        print("\nJSON Mode:")
        print(f"  Sent:     {TestChatClient.json_send_bytes} bytes")
        print(f"  Received: {TestChatClient.json_receive_bytes} bytes")
        print(f"  Total:    {TestChatClient.json_send_bytes + TestChatClient.json_receive_bytes} bytes")

        return result


#these don't include TCP/IP headers, which don't change much between the methods, but they would add like +40 bytes of overhead
if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestChatClient)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)

