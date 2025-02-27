import grpc
import hashlib
import timesystem_pb2
import timesystem_pb2_grpc

class Client:

    def __init__(self):
        """Initialize the client."""

        self.channel = None
        self.stub = None
        self.username = None
     

    def set_recipient(self, recipient):
        """Stores the default recipient locally so that future send_messages calls can use it.
        This is also convenient because you can change the intended recipient in the GUI at will here.
        """
        
        self.recipient = recipient
        print(f"Default recipient set to {recipient}")


    def ReceiveMessages(self):
        """
        Opens a streaming RPC to receive messages in real time.
        This blocks and yields messages to the GUI as they arrive.
        """

        request = timesystem_pb2.ReceiveMessagesRequest(username=self.username)
        try:
            for chat_msg in self.stub.ReceiveMessages(request):
                message_str = f"Received from {chat_msg.sender}: {chat_msg.message}"
                print(message_str) #so i can debug from terminal lol
                return message_str
        except grpc.RpcError as e:
            print("Message stream closed:", e)
    

    def send_messages(self, recipient, message):
        """
        Sends a message by calling the SendMessage RPC.

        Returns:
            the message data that is displayed in the GUI.
        """

        #if the recipient doesn't exist yet 
        if not hasattr(self, "recipient") or not self.recipient:
            print("No recipient set.")
            return False
    
        request = timesystem_pb2.SendMessageRequest(sender=self.username, recipient=recipient, message=message)
        response = self.stub.SendMessage(request)
        print("Server response:", response.message)
        return response.delivered
            

    def start_client(self):
        """Responsible for booting up the client and establishing the first connection to the server. Connects to the server on a localhost port.

        Args:
            host (str): The server IP or hostname. We can text each other over not as strongly encrypted wifi like 'Harvard University'. Eduroam might be too encrypted lol.
            port (int): The server's designated listening port. This is assigned in the server as '50051'
        """

        try:
            host = input("Enter the server host: ")
            port = input("Enter the server port: ")
            self.channel = grpc.insecure_channel(f'{host}:{port}')
            self.stub = timesystem_pb2_grpc.CommunicationServiceStub(self.channel)
            print("Connected to the server.")

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                print("Server is unavailable. Try again later.")

        except Exception as e: 
            print(f"Failed to connect to the gRPC server: {e}. Client needs to retry.")



def start_client(client_instance):
    """Function to start the client outside of the Client object."""
    client_instance.start_client()

if __name__ == "__main__":
    client = Client()
    start_client(client)