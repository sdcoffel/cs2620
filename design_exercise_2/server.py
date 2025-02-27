import grpc 
import queue
import re
import timesystem_pb2
import timesystem_pb2_grpc
from concurrent import futures 
# from accounts import *
# from messages import *

#GLOBALS - DO NOT MOVE
# PENDING_MESSAGES_FILE_PATH = "pending_messages.txt"
active_clients = {}
# pending_messages = {}

class ChatServer(timesystem_pb2_grpc.CommunicationServiceServicer):

    def SendMessage(self, request, context):
        """This function will send a message to a specific client. 
        If the intended recipient is online, the message is delivered in real time by placing it into that client's queue.
        If the recipient is offline, the message is appended to the 'pending_messages' store and saved to persistent storage, so it can be delivered when the recipient logs in.

        Args:
            request (SendMessageRequest): A request message containing:
                - sender (str): The username of the client sending the message.
                - recipient (str): The username of the intended recipient.
                - message (str): The content of the message.
                - context (grpc.ServicerContext): context for the RPC call

        Returns:
            SendMessageResponse: A response message indicating whether the message was delivered in real time (delivered=True) or saved as pending (delivered=False).
        """

        #if the recipient is online, i.e., their queue is active, deliver in real time.
        if request.recipient in active_clients:
            client_queue = active_clients[request.recipient]
            client_queue.put((request.sender, request.message))

            print(f"{request.sender} is messaging {request.recipient}.")
            print(f"Message from {request.sender} to {request.recipient} delivered.")

            return timesystem_pb2.SendMessageResponse(delivered=True, message="Message delivered.")
        
        else:
            #store to pending messages if intended recipient is not online
            if request.recipient not in pending_messages:
                pending_messages[request.recipient] = []

            pending_messages[request.recipient].append((request.sender, request.message))
            print(f"Message from {request.sender} to {request.recipient} saved as pending.")
            return timesystem_pb2.SendMessageResponse(delivered=False, message="Recipient offline. Message saved as pending.")


    def ReceiveMessages(self, request, context):
        """
        Server-streaming RPC that continuously yields new chat messages for the user.
        Ensures that the user's message queue exists and queues any pending messages from persistent storage. 
        When a message is available, this yields a ChatMessageResponse containing the sender and message content. The loop continues as long as the RPC context is active.
        
        Args:
            request (ReceiveMessagesRequest): The request message containing:
                - username (str): The username of the client that will receive messages.
                - context (grpc.ServicerContext):  RPC-specific info
            
        Yields:
            ChatMessageResponse: A stream of chat messages (each with a sender and message field) for the client.
        """
        #make sure the user's queue is actually there
        if request.username not in active_clients:
            active_clients[request.username] = queue.Queue()
        client_queue = active_clients[request.username]

        #pending messages get added to the queue
        if request.username in pending_messages:
            for sender, msg in pending_messages[request.username]:
                client_queue.put((sender, msg))
            pending_messages[request.username] = []
            #delete_pending_messages(PENDING_MESSAGES_FILE_PATH, request.username, 10) 

        #stream messages to the client in real time. if we ever happen to hit an empty queue, just continue 
        while context.is_active():
            try:
                sender, msg = client_queue.get(timeout=0) #immediate - although i want to clean this up a lot
                yield timesystem_pb2.ChatMessageResponse(sender=sender, message=msg)

            except queue.Empty:
                continue


def start_server():
    """Boots up and runs the gRPC server until termination.
    This function:
      - Loads any pending messages from persistent storage.
      - Creates a gRPC server using a ThreadPoolExecutor with up to 10 worker threads.
      - Binds the server to port 50051 and starts it.
      - Calls wait_for_termination() to block execution until a termination signal (e.g., KeyboardInterrupt) is received.

    Upon termination (Cntrl+C for us), the function attempts to save any pending messages back to persistent storage before exiting.

    Returns:
        None
    """

    global pending_messages
    #load_pending_messages(PENDING_MESSAGES_FILE_PATH)
    print("Pending messages loaded...")

    try:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        timesystem_pb2_grpc.add_CommunicationServiceServicer_to_server(ChatServer(), server)
        server.add_insecure_port('0.0.0.0:50051')
        server.start()
        print(f"Server is listening on port 50051...")
        server.wait_for_termination() #this is a blocking call that keeps the server running until keyboard interrupt

    except Exception as e: 
        print(f"Fatal error {e} with server")

    finally:
        try:
            #save_pending_messages(PENDING_MESSAGES_FILE_PATH, pending_messages)
            print("Pending messages saved...")

        except Exception as e:
            print(f"Failed to exit server properly! : {e}")


if __name__ == "__main__":
    """Call all globally scoped variables, and start up the server."""

    #PENDING_MESSAGES_FILE_PATH
    active_clients 
    #pending_messages 
    start_server()