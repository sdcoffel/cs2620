import threading
import time
import grpc
import chatapp_pb2
import chatapp_pb2_grpc

"""
Class coverage for RaftNodes, and the services that you can provide with them via RaftService. 
These classes are used to implement the Raft consensus algorithm, which helps us manage the 
replicated servers and decide who will be elected the next leader in the event of a failure.

RaftNode:
  - election_loop: background thread that handles the election process
  - send_request_vote: sends a RequestVote RPC to a peer
  - send_heartbeats: sends AppendEntries RPCs to all peers
  - is_leader: returns True if the node is the leader
  - get_leader: returns the leader's ID
  - add_peer: adds a new peer to the node

RaftService:
  - RequestVote: gRPC service for RequestVote RPC 
"""

# Global Raft node instance set per server instance
raft_node = None

class RaftNode:
    """
    The RaftNode class is responsible for managing the behavior of a single server in a Raft cluster.
    It tracks the server's role (follower, candidate, or leader), handles election timeouts, 
    conducts leadership elections, and sends periodic heartbeats (AppendEntries RPC calls) to other servers.

    Attributes:
        server_id (str): Unique identifier for this server (e.g., "server1").
        peers (list): A list of gRPC addresses (strings) for other servers in the cluster.
        role (str): The current role of this server ("follower", "candidate", or "leader").
        address (str): The gRPC address of this server.
        current_term (int): The current term number for this server in the Raft protocol.
        voted_for (str): The candidate ID that this server voted for in the current term (None if no vote).
        leader_id (str): The ID of the current leader (if known).
        last_heartbeat (float): The timestamp of the last received heartbeat from a leader (or since it became leader).
        election_timeout (float): The duration in seconds without a heartbeat before triggering an election.
        lock (threading.Lock): Thread lock used to protect shared state in the server.
        global_leader (multiprocessing.Value or similar): A shared value indicating the global leader's ID
                                                         if known/exists in this cluster setup.
    """

    def __init__(self, server_id, peers, address, timeout, global_leader):
        """
        Initialize a new RaftNode.

        Args:
            server_id (str): The unique identifier for this server (e.g., "server1").
            peers (list): A list of gRPC addresses for other servers in the cluster.
            address (str): The gRPC address of this server.
            timeout (float): The election timeout duration in seconds.
            global_leader: A shared value or any structure that holds the current leader's ID globally 
                           (could be a multiprocessing.Value or similar synchronization primitive).
        """
        self.server_id = server_id
        self.peers = peers  # list of all addresses other than this node
        self.role = "follower"  # roles: follower, candidate, leader
        self.address = address  # node's address - where the server lives
        self.current_term = 0
        self.voted_for = None
        self.leader_id = None
        self.last_heartbeat = time.time()
        self.election_timeout = timeout  # fixed timeout length
        self.lock = threading.Lock()
        self.global_leader = global_leader

        # Default to having server1 be the first leader, for demonstration or initial setup.
        if self.server_id == "server1":
            self.role = "leader"
            self.global_leader_id = self.server_id
            global_leader = self.server_id
            print(f"Node {self.server_id} is set as leader on startup.")
        
        # The election loop runs in a background thread.
        threading.Thread(target=self.election_loop, daemon=True).start()
        
    def election_loop(self):
        """
        This background thread method checks for leadership status and election timeouts.
        If no valid leader is detected and the election timeout passes, the node transitions 
        to 'candidate' and starts a new election by incrementing its term and sending 
        RequestVote RPCs to peers. If it gains a majority, it becomes the leader.
        """
        while True:
            time.sleep(0.1)

            with self.lock:
                # Check if a global leader is set
                if self.global_leader.value is not None:
                    # If the global leader is not this server, become a follower and update leader info
                    if self.global_leader.value != self.server_id:
                        if self.role == "leader":
                            print(f"Node {self.server_id} stepping down from leader role to follower.")
                        self.role = "follower"
                        self.leader_id = self.global_leader.value
                        self.last_heartbeat = time.time()
                        continue
                    
                    # If the global leader is this node, send heartbeats if we're the leader
                    if self.role == "leader":
                        self.send_heartbeats()
                        continue

                # If no global leader is designated, check for election timeout
                if time.time() - self.last_heartbeat > self.election_timeout:
                    # Trigger election process when there is no leader
                    print(f"Leader node has failed. Node {self.server_id} starting election for term {self.current_term}")
                    self.role = "candidate"
                    self.current_term += 1
                    self.voted_for = self.server_id
                    votes = 1  # Vote for self

                    # Send RequestVote RPC to all peers
                    for peer in self.peers:
                        try:
                            vote_granted = self.send_request_vote(peer, self.current_term)
                            if vote_granted:
                                votes += 1
                        except Exception as e:
                            # If there's an error connecting to a peer, just continue
                            continue

                    # Become the leader if we get majority votes
                    if votes > (len(self.peers) + 1) // 2:
                        self.role = "leader"
                        self.leader_id = self.server_id
                        self.global_leader.value = self.server_id
                        print(f"Node {self.server_id} is the new leader for term {self.current_term}")
                    else:
                        # Otherwise, revert to follower and reset heartbeat timer
                        self.role = "follower"
                        self.last_heartbeat = time.time()

    def send_request_vote(self, peer, term):
        """
        Send a RequestVote RPC to the specified peer.

        Args:
            peer (str): The gRPC address of the peer to request a vote from.
            term (int): The current term of this server (candidate).

        Returns:
            bool: True if the peer grants a vote, False otherwise.
        """
        try:
            # Open a gRPC channel to the peer
            with grpc.insecure_channel(peer) as channel:
                stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                # Build the RequestVoteRequest
                request = chatapp_pb2.RequestVoteRequest(
                    term=term,
                    candidate_id=self.server_id,
                    last_log_index=0,  # No logs maintained here
                    last_log_term=0    # No logs maintained here
                )
                # Send the RPC and await response with a short timeout
                response = stub.RequestVote(request, timeout=2)
                print(f"Node {self.server_id} got vote_granted={response.vote_granted} "
                      f"from {peer} for term {term}")
                return response.vote_granted
        except Exception as e:
            print(f"Error sending RequestVote from {self.server_id} to {peer}: {e}")
            return False

    def send_heartbeats(self):
        """
        Send AppendEntries RPC (heartbeats) to all peers to maintain leadership.
        This method is only called if the node's role is 'leader'. It also 
        updates the local 'last_heartbeat' timestamp to prevent unnecessary 
        election cycles.
        """
        # Only leaders send heartbeats
        if self.role != "leader":
            return  # Followers don't send heartbeats

        # Update local heartbeat timestamp
        self.last_heartbeat = time.time()
        
        # For each peer, send an AppendEntries RPC as a heartbeat
        for peer in self.peers:
            if peer == self.address:
                # Don't send a request to yourself
                continue
            try:
                #print(f"Sending heartbeat to {peer}...") #for sanity checking - uncomment this for debugging
                with grpc.insecure_channel(peer) as channel:
                    stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                    # Build the AppendEntriesRequest message (empty entries for a heartbeat)
                    request = chatapp_pb2.AppendEntriesRequest(
                        term=self.current_term,
                        leader_id=self.server_id,
                        prev_log_index=0,  # Not maintaining logs here
                        prev_log_term=0,   # Not maintaining logs here
                        entries=[],        # Empty heartbeat
                        leader_commit=0    # No commit index to maintain
                    )
                    response = stub.AppendEntries(request, timeout=0.5)
                    if not response.success:
                        print(f"Heartbeat to {peer} failed: response={response}")
            except Exception as e:
                #print(f"Error sending heartbeat from {self.server_id} to {peer}: {e}")
                print(f"Retrying heartbeat to {peer}...")
                time.sleep(1)  # Wait before retrying
                try:
                    with grpc.insecure_channel(peer) as channel:
                        stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                        response = stub.AppendEntries(request, timeout=0.5)
                        if response.success:
                            print(f"Retry successful: Heartbeat to {peer} succeeded.")
                except Exception as retry_exception:
                    print(f"Retry failed: Could not send heartbeat to {peer}: {retry_exception}")


        # Sleep for 2 seconds before sending the next heartbeat
        time.sleep(2)

    def is_leader(self):
        """
        Check if this node is the current leader.

        Returns:
            bool: True if this server is the leader, False otherwise.
        """
        with self.lock:
            return self.role == "leader"

    def get_leader(self):
        """
        Get the leader ID for the cluster from this node's perspective.

        Returns:
            str or None: The leader ID if this node knows it, else None.
        """
        with self.lock:
            return self.leader_id if self.role != "follower" else None

    def add_peer(self, peer_address):
        """
        Add a new peer to the Raft node.

        This method takes in the address of a new peer and appends it to 
        the list of known peers if it is not already present. This ensures 
        the new server will receive heartbeats, participate in voting, and 
        stay consistent with the cluster.
        """
        with self.lock:
            if peer_address not in self.peers:
                self.peers.append(peer_address)
                print(f"Added new peer: {peer_address}")
                #delay for the server to properly initialize before it recieves heartbeats
                time.sleep(3)


class RaftService(chatapp_pb2_grpc.RaftServiceServicer):
    """
    The RaftService class implements the gRPC servicer for handling Raft RPCs:
    RequestVote, AppendEntries, Ping, and AddServer. It delegates actual Raft 
    logic to the RaftNode instance passed in at initialization.
    """

    def __init__(self, raft_node):
        """
        Initialize a new RaftService with a given RaftNode.

        Args:
            raft_node (RaftNode): The RaftNode instance containing the Raft logic.
        """
        self.raft_node = raft_node
    
    def RequestVote(self, request, context):
        """
        gRPC service method for the RequestVote RPC. This method updates 
        the raft_node state if necessary (e.g., resets the election timer). 
        Currently, it simply grants the vote for demonstration, 
        but normally you would add logic to validate terms, logs, etc.

        Args:
            request (RequestVoteRequest): The incoming vote request from a candidate.
            context: gRPC context (unused here).

        Returns:
            RequestVoteResponse: A response indicating the term and whether the vote is granted.
        """
        # Updates the raft_node state if necessary (e.g., reset election timer).
        return chatapp_pb2.RequestVoteResponse(term=request.term, vote_granted=True)

    def AppendEntries(self, request, context):
        """
        gRPC service method for the AppendEntries RPC (used for heartbeats).

        This method resets the heartbeat timer of the local node, updates the 
        local leader information, and forces the node to become a follower if 
        the RPC is coming from a valid leader.

        Args:
            request (AppendEntriesRequest): The incoming AppendEntries request (heartbeat).
            context: gRPC context (unused here).

        Returns:
            AppendEntriesResponse: A response indicating the term and whether the append 
                                   was successful (usually True for heartbeats).
        """
        # Reset heartbeat timer
        with self.raft_node.lock:
            self.raft_node.last_heartbeat = time.time()

            # If this call comes from a valid leader, update that leader's info
            self.raft_node.leader_id = request.leader_id
            self.raft_node.role = "follower"
        return chatapp_pb2.AppendEntriesResponse(term=request.term, success=True)

    def Ping(self, request, context):
        """
        A simple gRPC method that can be used for health checks or to get 
        status information about the server.

        Args:
            request (PingRequest): The incoming request (unused here).
            context: gRPC context (unused here).

        Returns:
            PingResponse: A response containing the status and the server's role.
        """
        # Get the current status if we need it
        return chatapp_pb2.PingResponse(status="OK", role=self.raft_node.role)

    def AddServer(self, request, context):
        """
        Handle the addition of a new server to the cluster.

        This gRPC service method takes the address of the new server from 
        the request and calls the RaftNode's add_peer method to include 
        it in the cluster.
        """
        new_server_id = request.server_id
        new_server_address = request.address

        print(f"Remote server '{new_server_id}' at {new_server_address} is attempting to connect to the cluster.")
        self.raft_node.add_peer(new_server_address)
        return chatapp_pb2.AddServerResponse(success=True)