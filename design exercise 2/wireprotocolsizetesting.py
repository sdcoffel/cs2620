"""
wireprotocolsizetesting.py
--------------------------
Measuring gRPC Protobuf 'payload' sizes by calling the actual client methods.
"""

import unittest
from unittest.mock import patch, MagicMock

import chatapp_pb2
import chatapp_pb2_grpc

# Import your new gRPC-based client
from client import Client


class TestChatClient(unittest.TestCase):
    """
    A test suite that measures:
      - Protobuf request sizes (as 'sent' bytes)
      - Protobuf response sizes (as 'received' bytes)

    We patch client.chatapp_pb2_grpc.ChatServiceStub to simulate the server
    in the exact same place that the client references the stub.
    """

    proto_send_bytes = 0
    proto_receive_bytes = 0

    def setUp(self):
        """Initialize the client before each test."""
        self.client = Client()

    def tearDown(self):
        """Clean up after each test."""
        pass

    @patch("client.chatapp_pb2_grpc.ChatServiceStub")  # <--- Not autospec
    def test_send_messages_proto_mode(self, mock_stub_class):
        """
        Test measuring the byte size of a SendMessage request/response
        when calling the client's send_messages().
        """
        # mock_stub_class is the mock constructor for ChatServiceStub
        mock_stub = mock_stub_class.return_value
        self.client.stub = mock_stub

        # Build a fake server response
        fake_response = chatapp_pb2.SendMessageResponse(
            delivered=True, message="Message delivered."
        )
        # The mock's SendMessage returns this response
        mock_stub.SendMessage.return_value = fake_response

        # "Log in" the client
        self.client.username = "alice"
        self.client.set_recipient("bob")

        # Actually call the client's method
        self.client.send_messages("bob", "Hello from Protobuf!")

        # Confirm the stub method was called
        mock_stub.SendMessage.assert_called_once()
        # Extract the actual request used
        (actual_request,), _ = mock_stub.SendMessage.call_args

        # Measure request size
        req_bytes = actual_request.SerializeToString()
        self.__class__.proto_send_bytes += len(req_bytes)

        # Measure response size
        resp_bytes = fake_response.SerializeToString()
        self.__class__.proto_receive_bytes += len(resp_bytes)

    @patch("client.chatapp_pb2_grpc.ChatServiceStub")  # <--- Not autospec
    def test_receive_messages_proto_mode(self, mock_stub_class):
        """
        Test measuring the byte size of a ReceiveMessages server-streaming call
        by calling the client's ReceiveMessages() generator.
        """
        mock_stub = mock_stub_class.return_value
        self.client.stub = mock_stub

        # Simulate the server streaming these responses:
        fake_stream = [
            chatapp_pb2.ChatMessageResponse(sender="alice", message="Hi Bob!"),
            chatapp_pb2.ChatMessageResponse(sender="charlie", message="Lunch soon?"),
        ]
        # Make the stub's ReceiveMessages return an iterator over those
        mock_stub.ReceiveMessages.return_value = iter(fake_stream)

        # Suppose the client is "bob"
        self.client.username = "bob"

        # Now call the client's method that consumes the server stream
        stream = self.client.ReceiveMessages()

        # The client’s code calls stub.ReceiveMessages(...) under the hood
        # We'll iterate to collect the results
        collected = []
        for msg in stream:
            collected.append(msg)
            # Once we've read all messages, we can break
            if len(collected) == len(fake_stream):
                break

        mock_stub.ReceiveMessages.assert_called_once()
        (actual_request,), _ = mock_stub.ReceiveMessages.call_args

        # Measure the request
        req_bytes = actual_request.SerializeToString()
        self.__class__.proto_send_bytes += len(req_bytes)

        # Measure all responses
        for resp in fake_stream:
            resp_bytes = resp.SerializeToString()
            self.__class__.proto_receive_bytes += len(resp_bytes)


class CustomTestRunner(unittest.TextTestRunner):
    """
    Custom test runner that prints how many bytes we 'sent' and 'received'
    over our Protobuf-based calls across all tests.
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
