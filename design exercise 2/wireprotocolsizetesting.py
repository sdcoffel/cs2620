"""
sizetesting.py
---------------
Measuring gRPC Protobuf 'payload' sizes to compare with the old JSON vs Plain approach.
"""

import unittest
from unittest.mock import patch

# Import your proto modules
import chatapp_pb2
import chatapp_pb2_grpc

# Import your new gRPC-based client
from client import Client


class TestChatClient(unittest.TestCase):
    """
    A test suite that measures:
      - Protobuf request sizes (as 'sent' bytes)
      - Protobuf response sizes (as 'received' bytes)

    We patch the ChatServiceStub to simulate the server and capture
    how large (in bytes) the serialized messages would be.
    """

    # Class-level counters that accumulate over all tests
    proto_send_bytes = 0
    proto_receive_bytes = 0

    def setUp(self):
        """Initialize the client before each test."""
        self.client = Client()
        # If needed, call self.client.start_client("localhost", 50051)
        # but we'll patch the stub so it’s not strictly required here.

    def tearDown(self):
        """Clean up after each test."""
        # If there was anything like channel shutdown, do it here.
        pass

    @patch("chatapp_pb2_grpc.ChatServiceStub", autospec=True)
    def test_send_messages_proto_mode(self, mock_stub_class):
        """
        Test that we can measure the byte size of a SendMessage request/response.
        """
        # Create the mock stub that your client code uses.
        mock_stub = mock_stub_class.return_value

        # Build a fake response from the server:
        fake_response = chatapp_pb2.SendMessageResponse(
            delivered=True, message="Message delivered."
        )
        mock_stub.SendMessage.return_value = fake_response

        # Construct the request you want the client to send
        request = chatapp_pb2.SendMessageRequest(
            sender="alice", recipient="bob", message="Hello from Protobuf!"
        )

        # Measure request size (what we "send" to the server)
        request_bytes = request.SerializeToString()
        self.__class__.proto_send_bytes += len(request_bytes)

        # Simulate making the call via the client's actual method (or directly):
        response = mock_stub.SendMessage(request)

        # Measure response size (what we "receive" from the server)
        response_bytes = response.SerializeToString()
        self.__class__.proto_receive_bytes += len(response_bytes)

        # Check that the stub was called as expected
        mock_stub.SendMessage.assert_called_once()

    @patch("chatapp_pb2_grpc.ChatServiceStub", autospec=True)
    def test_receive_messages_proto_mode(self, mock_stub_class):
        """
        Test measuring the byte size of a ReceiveMessages server-streaming call.
        """
        mock_stub = mock_stub_class.return_value

        # Fake streaming responses:
        fake_stream = [
            chatapp_pb2.ChatMessageResponse(sender="alice", message="Hi there!"),
            chatapp_pb2.ChatMessageResponse(
                sender="bob", message="Don't forget the meeting."
            ),
        ]
        # Return an iterator of these messages when stub.ReceiveMessages() is called
        mock_stub.ReceiveMessages.return_value = iter(fake_stream)

        # Construct the request
        request = chatapp_pb2.ReceiveMessagesRequest(username="bob")
        request_bytes = request.SerializeToString()
        self.__class__.proto_send_bytes += len(request_bytes)

        # The client code would normally iterate over the server stream.
        # Here we just collect them all so we can measure them.
        responses = list(mock_stub.ReceiveMessages(request))
        for resp in responses:
            self.__class__.proto_receive_bytes += len(resp.SerializeToString())

        mock_stub.ReceiveMessages.assert_called_once()


class CustomTestRunner(unittest.TextTestRunner):
    """
    Custom test runner that prints how many bytes we 'sent' and 'received' over our Protobuf-based calls.
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

        print("\nDetailed Byte Size Totals (Protobuf Payload Only):")

        sent = TestChatClient.proto_send_bytes
        received = TestChatClient.proto_receive_bytes

        print("\nProtobuf Mode:")
        print(f"  Sent:     {sent} bytes")
        print(f"  Received: {received} bytes")
        print(f"  Total:    {sent + received} bytes\n")

        return result


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestChatClient)
    runner = CustomTestRunner(verbosity=2)
    runner.run(suite)
