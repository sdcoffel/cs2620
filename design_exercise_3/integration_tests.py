import time
import sys
import pytest
import grpc
from raftnode import RaftNode

#run with: pytest -s --maxfail=1 --disable-warnings -v --cov=raftnode integration_tests.py

# Dummy global container for shared leader state.
class DummyGlobal:
    def __init__(self, value=None):
        self.value = value

# Define a fake callable to simulate a unary RPC.
class FakeUnaryUnaryMultiCallable:
    def __init__(self, func):
        self.func = func
    def __call__(self, request, timeout=None, **kwargs):
        return self.func(request, timeout)

# Define a fake channel that implements the expected gRPC interface.
class FakeChannel:
    # Add a killed_nodes set to track which nodes should be considered "dead"
    killed_nodes = set()
    
    def unary_unary(self, method, request_serializer=None, response_deserializer=None, **kwargs):
        if "RequestVote" in method:
            # Simulate a RequestVote RPC always granting a vote.
            return FakeUnaryUnaryMultiCallable(
                lambda request, timeout=None: 
                    # Don't grant votes to killed nodes
                    type("FakeResponse", (), {"vote_granted": request.candidate_id not in FakeChannel.killed_nodes})()
            )
        elif "AppendEntries" in method:
            # Simulate an AppendEntries (heartbeat) RPC always succeeding.
            return FakeUnaryUnaryMultiCallable(
                lambda request, timeout=None: 
                    # Don't accept heartbeats from killed nodes
                    type("FakeResponse", (), {"success": request.leader_id not in FakeChannel.killed_nodes})()
            )
        elif "Ping" in method:
            # Simulate a Ping RPC.
            return FakeUnaryUnaryMultiCallable(
                lambda request, timeout=None: type("FakeResponse", (), {"status": "OK", "role": "follower"})()
            )
        else:
            # For any other method, return a generic dummy response.
            return FakeUnaryUnaryMultiCallable(
                lambda request, timeout=None: type("FakeResponse", (), {})()
            )
    def close(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# Monkey-patched insecure_channel to return our FakeChannel.
def fake_insecure_channel(peer):
    return FakeChannel()

@pytest.mark.integration
def test_chaos_election(monkeypatch):
    """
    Integration test:
      - Create a cluster of three Raft nodes.
      - Initially, server1 is leader.
      - Simulate chaos by "killing" server1 (disabling its heartbeats and forcing a stale heartbeat)
        and resetting the global leader.
      - The remaining nodes should trigger an election and promote either server2 or server3 as leader.
    """
    # Use our fake insecure_channel for all gRPC calls.
    monkeypatch.setattr(grpc, "insecure_channel", fake_insecure_channel)

    # Shared global leader container.
    global_leader = DummyGlobal("server1")

    # Instantiate three nodes with a short election timeout to speed up the test.
    node1 = RaftNode(
        server_id="server1",
        peers=["localhost:50052", "localhost:50053"],
        address="localhost:50051",
        timeout=0.5,
        global_leader=global_leader
    )
    node2 = RaftNode(
        server_id="server2",
        peers=["localhost:50051", "localhost:50053"],
        address="localhost:50052",
        timeout=0.5,
        global_leader=global_leader
    )
    node3 = RaftNode(
        server_id="server3",
        peers=["localhost:50051", "localhost:50052"],
        address="localhost:50053",
        timeout=0.5,
        global_leader=global_leader
    )

    # Allow the nodes some time to stabilize. Initially, server1 should be leader.
    time.sleep(1)
    assert global_leader.value == "server1"

    # Simulate chaos: "kill" node1 by disabling its heartbeat and forcing a stale heartbeat.
    node1.send_heartbeats = lambda: None  # disable heartbeats for node1
    node1.last_heartbeat = time.time() - 2  # force stale heartbeat
    
    # Add server1 to the killed_nodes set so it can't get votes or have its heartbeats accepted
    FakeChannel.killed_nodes.add("server1")
    
    # Reset the global leader to simulate leader failure.
    global_leader.value = None

    # Wait for the remaining nodes to detect the failure and trigger an election.
    time.sleep(2)

    # Assert that a new leader (server2 or server3) has been elected.
    assert global_leader.value in ["server2", "server3"], (
        f"Expected leader to be server2 or server3, got {global_leader.value}"
    )
    print(f"New leader elected: {global_leader.value}")
    
    # Clean up the killed_nodes set for other tests
    FakeChannel.killed_nodes.clear()



@pytest.mark.integration
def test_repeated_chaos_elections(monkeypatch):
    """
    Repeated chaos test:
      - Create a cluster of three nodes.
      - For several rounds, simulate failure of the current leader,
        wait for a new election, and then restore the failed node.
      - Assert that in each round a new leader (different from the one killed) is elected.
    """
    monkeypatch.setattr(grpc, "insecure_channel", fake_insecure_channel)
    global_leader = DummyGlobal("server1")

    node1 = RaftNode(
        server_id="server1",
        peers=["localhost:50052", "localhost:50053"],
        address="localhost:50051",
        timeout=0.5,
        global_leader=global_leader
    )
    node2 = RaftNode(
        server_id="server2",
        peers=["localhost:50051", "localhost:50053"],
        address="localhost:50052",
        timeout=0.5,
        global_leader=global_leader
    )
    node3 = RaftNode(
        server_id="server3",
        peers=["localhost:50051", "localhost:50052"],
        address="localhost:50053",
        timeout=0.5,
        global_leader=global_leader
    )

    # Allow initial stabilization.
    time.sleep(1)
    assert global_leader.value == "server1"
    rounds = 5

    for i in range(rounds):
        current_leader = global_leader.value
        print(f"Round {i}: Current leader is {current_leader}")
        if current_leader == "server1":
            failing_node = node1
        elif current_leader == "server2":
            failing_node = node2
        elif current_leader == "server3":
            failing_node = node3
        else:
            pytest.fail("No leader found at start of round.")

        # Save the original heartbeat method if not already saved.
        if not hasattr(failing_node, "_original_send_heartbeats"):
            failing_node._original_send_heartbeats = failing_node.send_heartbeats

        # Simulate failure: disable heartbeat and force stale timestamp.
        failing_node.send_heartbeats = lambda: None
        failing_node.last_heartbeat = time.time() - 2
        
        # Add the failing node to the killed_nodes set
        FakeChannel.killed_nodes.add(current_leader)
        
        global_leader.value = None

        # Wait for an election to occur.
        time.sleep(2)
        new_leader = global_leader.value
        print(f"Round {i}: New leader is {new_leader}")
        assert new_leader in ["server1", "server2", "server3"], (
            f"Expected new leader to be one of the nodes; got {new_leader}"
        )
        assert new_leader != current_leader, (
            f"Round {i}: New leader {new_leader} should differ from old leader {current_leader}"
        )

        # Restore the failing node's heartbeat method.
        failing_node.send_heartbeats = failing_node._original_send_heartbeats
        
        # Remove the node from the killed_nodes set
        FakeChannel.killed_nodes.remove(current_leader)

    print("Repeated chaos elections test passed.")

#-------------------------------------------------------------------------
# Run tests with pytest and measure coverage for chatserver and raftnode.
#-------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(pytest.main([
        "-v",
        "--maxfail=1",
        "--cov=chatserver",
        "--cov=raftnode",
        __file__
    ]))
