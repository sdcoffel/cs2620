import threading 
import time 
import grpc
import chatapp_pb2
import chatapp_pb2_grpc

"""
Class coverage for RaftNodes, and the services that you can provide with them via RaftService. 
These classes are used to implement the Raft consensus algorithm, which helps us manage the replicated servers and decide who will 
be elected the next leader in the event of a failure.

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

#global Raft node instance set per serverinstance
raft_node = None

class RaftNode:
    def __init__(self, server_id, peers, address, timeout, global_leader):
        self.server_id = server_id
        self.peers = peers  #list of all addresses other than that node
        self.role = "follower"  # roles: follower, candidate, leader
        self.address = address  #node's address - where the server lives - needs to be updated by the zookeeper modules
        self.current_term = 0
        self.voted_for = None
        self.leader_id = None
        self.last_heartbeat = time.time()
        self.election_timeout = timeout #fixed timeout length that i can override if i need to
        self.lock = threading.Lock()
        self.global_leader = global_leader

        #default to having server1 be the first leader
        if self.server_id == "server1":
            self.role = "leader"
            self.global_leader_id = self.server_id
            global_leader = self.server_id
            print(f"Node {self.server_id} is set as leader on startup.")
        
        #election loop is in a background thread
        threading.Thread(target=self.election_loop, daemon=True).start()
        
        
    def election_loop(self):
        while True:
            time.sleep(0.1)
            with self.lock:
                if self.global_leader.value is not None:
                    if self.global_leader.value != self.server_id:
                        if self.role == "leader":
                            print(f"Node {self.server_id} stepping down from leader role to follower.")
                        self.role = "follower"
                        self.leader_id = self.global_leader.value
                        self.last_heartbeat = time.time()
                        continue
                    
                    #if the global leader is already this node, then send heartbeats
                    if self.role == "leader":
                        self.send_heartbeats()
                        continue

                #this is where the synchronization bug is happening 
                #if no global leader is designated, check for election timeout
                if time.time() - self.last_heartbeat > self.election_timeout:
                    #trigger election process when there is no leader
                    print(f"Leader node has failed. Node {self.server_id} starting election for term {self.current_term}")
                    self.role = "candidate"
                    self.current_term += 1
                    self.voted_for = self.server_id
                    votes = 1  # vote for self

                    for peer in self.peers:
                        try:
                            vote_granted = self.send_request_vote(peer, self.current_term)
                            if vote_granted:
                                votes += 1
                        except Exception as e:
                            continue

                    #become the leader if we get majority votes
                    if votes > (len(self.peers) + 1) // 2:
                        self.role = "leader"
                        self.leader_id = self.server_id
                        self.global_leader.value = self.server_id
                        print(f"Node {self.server_id} is the new leader for term {self.current_term}")
                    else:
                        self.role = "follower"
                        self.last_heartbeat = time.time()


    def send_request_vote(self, peer, term):
        try:
            #open a gRPC channel to the peer
            with grpc.insecure_channel(peer) as channel:
                stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                #build the RequestVoteRequest
                request = chatapp_pb2.RequestVoteRequest(
                    term=term,
                    candidate_id=self.server_id,
                    last_log_index=0,  #no need to maintain the logs here
                    last_log_term=0    #ditto
                )
                response = stub.RequestVote(request, timeout=2)
                print(f"Node {self.server_id} got vote_granted={response.vote_granted} from {peer} for term {term}")
                return response.vote_granted
        except Exception as e:
            print(f"Error sending RequestVote from {self.server_id} to {peer}: {e}")
            return False


    def send_heartbeats(self):
        #only leaders send heartbeats
        if self.role != "leader":
            return #followers don't send heartbeats
        
        #update local heartbeat timestamp
        self.last_heartbeat = time.time()
        #print(f"{self.server_id} heartbeat")
        
        #for each peer, send an AppendEntries RPC as a heartbeat
        for peer in self.peers:
            if peer == self.address:
                #don't send a request to yourself
                continue
            try:
                with grpc.insecure_channel(peer) as channel:
                    stub = chatapp_pb2_grpc.RaftServiceStub(channel)
                    #build the AppendEntriesRequest message by filling in request
                    #for a heartbeat, the entries list is empty,so leave as empty
                    request = chatapp_pb2.AppendEntriesRequest(
                        term=self.current_term,
                        leader_id=self.server_id,
                        prev_log_index=0,  #not maintaining logs here so keep at 0
                        prev_log_term=0,   #ditto
                        entries=[],        #empty heartbeat 
                        leader_commit=0    #ditto
                    )
                    response = stub.AppendEntries(request, timeout=2)
                    if not response.success:
                        print(f"Heartbeat to {peer} failed: response={response}")
            except Exception as e:
                print(f"Error sending heartbeat from {self.server_id} to {peer}: {e}")
        
        #sleep for 2 seconds before sending the next heartbeat
        time.sleep(2)


    def is_leader(self):
        with self.lock:
            return self.role == "leader"
    

    def get_leader(self):
        with self.lock:
            return self.leader_id if self.role != "follower" else None


    def add_peer(self, peer_address):
        """Add a new peer to the Raft node."""
        with self.lock:
            if peer_address not in self.peers:
                self.peers.append(peer_address)
                print(f"Added new peer: {peer_address}")



class RaftService(chatapp_pb2_grpc.RaftServiceServicer):
    def __init__(self, raft_node):
        self.raft_node = raft_node
    
    def RequestVote(self, request, context):
        #updates the raft_node state if necessary (e.g., reset election timer)
        return chatapp_pb2.RequestVoteResponse(term=request.term, vote_granted=True)
    

    def AppendEntries(self, request, context):
        #reset heartbeat timer
        with self.raft_node.lock:
            self.raft_node.last_heartbeat = time.time()

            #if this call comes from a valid leader, update that leader's info 
            self.raft_node.leader_id = request.leader_id
            self.raft_node.role = "follower"
        return chatapp_pb2.AppendEntriesResponse(term=request.term, success=True)
    

    def Ping(self, request, context):
        #get the current status if we need it 
        return chatapp_pb2.PingResponse(status="OK", role=raft_node.role)
    

    def AddServer(self, request, context):
        """Handle the addition of a new server to the cluster."""
        new_server_address = request.address
        self.raft_node.add_peer(new_server_address)
        return chatapp_pb2.AddServerResponse(success=True)

    