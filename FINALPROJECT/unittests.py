# unittests.py
import pytest
import json
import os
import math
import tempfile
import time
import numpy as np
import client
import server
import socket
# Assume client.py and server.py are in the same directory:
from server import TradingServer, load_json, save_json
from client import TradingClient
import stockpricemanager

clients_file='clients.txt'
stock_file='stocks.txt'
currency_file='currencies.txt'
# --- Helpers ---

def make_temp_files(tmp_path):
    stock_file = tmp_path / "stocks.json"
    currency_file = tmp_path / "currency.json"
    clients_file = tmp_path / "clients.json"
    # initialize with sample data
    save_json(str(stock_file), {"AAPL": 100.0, "TSLA": 200.0})
    save_json(str(currency_file), {})
    save_json(str(clients_file), {})
    return str(stock_file), str(currency_file), str(clients_file)



class DummyConn:
    def __init__(self):
        self.data = b""
    def sendall(self, b: bytes):
        self.data += b

class DummySock:
    def __init__(self, responses=None):
        self.sent = []
        self._responses = list(responses or [])
    def sendall(self, data: bytes):
        self.sent.append(data)
    def recv(self, bufsize):
        if self._responses:
            return self._responses.pop(0)
        return b''

########################################## ---------------------------- SERVERRRRRRRR ------------------------------#######################################

@pytest.fixture
def server(tmp_path):
    stock_file, currency_file, clients_file = make_temp_files(tmp_path)
    srv = TradingServer('localhost', 0, stock_file, currency_file, clients_file)
    srv.load_state()
    return srv, stock_file, currency_file, clients_file

def test_register_and_list(server):
    srv, sf, cf, cf2 = server
    conn = DummyConn()
    # register new user
    srv.process_request({"cmd":"register","user":"alice"}, conn, sf, cf, cf2)
    resp = json.loads(conn.data.decode())
    assert resp["status"] == "ok"
    # duplicate register
    conn.data = b""
    srv.process_request({"cmd":"register","user":"alice"}, conn, sf, cf, cf2)
    resp = json.loads(conn.data.decode())
    assert resp["status"] == "ok"
    assert "portfolio" in resp
    # list_symbols
    conn.data = b""
    srv.process_request({"cmd":"list_symbols"}, conn, sf, cf, cf2)
    resp = json.loads(conn.data.decode())
    assert set(resp["symbols"]) == {"AAPL","TSLA"}

def test_process_request_missing_buy_params(server):
    srv, sf, cf, cf2 = server
    conn = DummyConn()
    # missing user
    srv.process_request({"cmd":"buy","symbol":"AAPL","qty":10}, conn, sf, cf, cf2)
    assert b'"status":"error"' in conn.data and b'"msg":"user,symbol,qty required"' in conn.data
    conn.data = b""
    # missing symbol
    srv.process_request({"cmd":"sell","user":"bob","qty":5}, conn, sf, cf, cf2)
    assert b'"status":"error"' in conn.data and b'"msg":"user,symbol,qty required"' in conn.data
    conn.data = b""
    # missing qty
    srv.process_request({"cmd":"buy","user":"bob","symbol":"AAPL"}, conn, sf, cf, cf2)
    assert b'"status":"error"' in conn.data and b'"msg":"user,symbol,qty required"' in conn.data

def test_sell_not_enough_shares(server):
    srv, sf, cf, cf2 = server
    # register user with zero holdings
    srv.process_request({"cmd":"register","user":"charlie"}, DummyConn(), sf, cf, cf2)
    conn = DummyConn()
    srv.process_request({"cmd":"sell","user":"charlie","symbol":"AAPL","qty":1}, conn, sf, cf, cf2)
    assert b'"msg":"not enough shares"' in conn.data


def test_sell_all_shares_removes_symbol(server):
    srv, sf, cf, cf2 = server
    srv.process_request({"cmd":"register","user":"dana"}, DummyConn(), sf, cf, cf2)
    # buy 2 shares
    srv.process_request({"cmd":"buy","user":"dana","symbol":"TSLA","qty":2}, DummyConn(), sf, cf, cf2)
    # sell 2 shares
    conn = DummyConn()
    srv.process_request({"cmd":"sell","user":"dana","symbol":"TSLA","qty":2}, conn, sf, cf, cf2)
    resp = json.loads(conn.data.decode())
    assert resp["status"] == "ok"
    assert srv.client_info["dana"]["TSLA"][0] == 0


@pytest.mark.parametrize("cmd,qty,expected_shares", [
    ("buy", 10, 30),  # starting 20 + 10
    ("sell", 5, 15)  # starting 20 - 5
])
def test_buy_sell(server, cmd, qty, expected_shares):
    srv, sf, cf, cf2 = server
    srv.client_info.clear()
    # register
    srv.process_request({"cmd":"register","user":"bob"}, DummyConn(), sf, cf, cf2)
    # initial buy of 20 shares
    srv.process_request({"cmd":"buy","user":"bob","symbol":"AAPL","qty":20}, DummyConn(), sf, cf, cf2)
    conn = DummyConn()
    srv.process_request({"cmd":cmd,"user":"bob","symbol":"AAPL","qty":qty}, conn, sf, cf, cf2)
    port = srv.client_info["bob"]["AAPL"][0]
    assert port == expected_shares

def test_server_save_state(tmp_path):
    # Prepare files and server
    sf, cf, cf2 = make_temp_files(tmp_path)
    srv = TradingServer('h', 0, sf, cf, cf2)
    # Modify in-memory state
    srv.stock_info = {"GOOG": 1500.0}
    srv.currency_info = {"EUR": 0.9}
    srv.client_info = {"alice": {"AAPL": [10,100,0,0]}}
    # Call save_state
    srv.save_state()
    # Verify files
    assert load_json(sf, {}) == srv.stock_info
    assert load_json(cf, {}) == srv.currency_info
    assert load_json(cf2, {}) == srv.client_info


def test_handle_client_register_and_close(tmp_path):
    sf, cf, cf2 = make_temp_files(tmp_path)
    srv = TradingServer('localhost',0,sf,cf,cf2)
    srv.load_state()
    # Fake connection that sends a register request then closes
    class FakeConn:
        def __init__(self):
            self.sent=b""
            self.closed=False
            self._buf=[b'{"cmd":"register","user":"bob"}\n', b'']
        def recv(self, buf):
            return self._buf.pop(0)
        def sendall(self, data):
            self.sent+=data
        def close(self):
            self.closed=True
    conn = FakeConn()
    # Run handler
    srv.handle_client(conn, ('127.0.0.1',12345))
    # After handling, bob should be registered and connection closed
    assert 'bob' in srv.client_info
    assert conn.closed


def test_serve_forever(monkeypatch, tmp_path):
    sf, cf, cf2 = make_temp_files(tmp_path)
    srv = TradingServer('localhost',0,sf,cf,cf2)
    srv.load_state()
    # Track calls
    calls = []
    
    class FakeSrvSocket:
        def __init__(self, *args, **kwargs):
            self.bind_addr = None
            self.listen_called = False
            self.closed = False
            # one connection then break
            self._accepts = [(DummyConn(), ('127.0.0.1', 9999))]
        def bind(self, addr):
            self.bind_addr = addr
        def listen(self):
            self.listen_called = True
        def accept(self):
            if self._accepts:
                return self._accepts.pop(0)
            raise KeyboardInterrupt
        def close(self):
            self.closed = True
    
    # Monkeypatch socket.socket and handle_client & save_state
    monkeypatch.setattr(socket, 'socket', lambda *args, **kwargs: FakeSrvSocket())
    def fake_handle(conn, addr):
        calls.append(addr)
    monkeypatch.setattr(TradingServer, 'handle_client', fake_handle)
    saved = []
    monkeypatch.setattr(TradingServer, 'save_state', lambda self: saved.append(True))
    # Run serve_forever and catch KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        srv.serve_forever()
    
    assert srv.scheduler is not None
    assert srv.scheduler.queue is not None

def test_register_no_user_error(server):
    srv, sf, cf, cf2 = server
    conn = DummyConn()
    srv.process_request({"cmd":"register"}, conn, sf, cf, cf2)
    assert b'"status":"error"' in conn.data
    assert b'"msg":"no user"' in conn.data

def test_get_portfolio_no_user_error(server):
    srv, sf, cf, cf2 = server
    conn = DummyConn()
    srv.process_request({"cmd":"get_portfolio"}, conn, sf, cf, cf2)
    assert b'"status":"error"' in conn.data
    assert b'"msg":"user required"' in conn.data

def test_get_portfolio(server):
    srv, sf, cf, cf2 = server
    user = "carol"
    # register and buy
    srv.process_request({"cmd":"register","user":user}, DummyConn(), sf, cf, cf2)
    srv.process_request({"cmd":"buy","user":user,"symbol":"TSLA","qty":5}, DummyConn(), sf, cf, cf2)
    conn = DummyConn()
    srv.process_request({"cmd":"get_portfolio","user":user}, conn, sf, cf, cf2)
    resp = json.loads(conn.data.decode())
    assert resp["status"] == "ok"
    assert "TSLA" in resp["portfolio"]


def test_handle_client_bad_json(tmp_path):
    sf, cf, cf2 = make_temp_files(tmp_path)
    srv = TradingServer('localhost',0,sf,cf,cf2)
    srv.load_state()
    class FakeConnBad:
        def __init__(self):
            self.data = b""
            self.closed = False
            self._buf = [b'invalid_json\n', b'']
        def recv(self, buf):
            return self._buf.pop(0)
        def sendall(self, chunk):
            self.data += chunk
        def close(self):
            self.closed = True
    conn = FakeConnBad()
    srv.handle_client(conn, ('127.0.0.1',54321))
    assert b'"msg":"bad json"' in conn.data
    assert conn.closed


def test_federated_update_and_pull(server):
    srv, sf, cf, cf2 = server
    # simulate two clients existing
    srv.client_info = {"u1":{}, "u2":{}}
    # each sends an update; server aggregates immediately per update
    srv.process_request({"cmd":"update_model","user":"u1","weights":[1,2,3]}, DummyConn(), sf, cf, cf2)
    # after first, global_weights == [1,2,3]
    assert srv.global_weights == [1.0,2.0,3.0]
    srv.process_request({"cmd":"update_model","user":"u2","weights":[3,2,1]}, DummyConn(), sf, cf, cf2)
    # after second, global_weights overwritten to [3,2,1]
    assert srv.global_weights == [3.0,2.0,1.0]
    # pull via get_global_model
    conn = DummyConn()
    srv.process_request({"cmd":"get_global_model"}, conn, sf, cf, cf2)
    resp = json.loads(conn.data.decode())
    assert resp["weights"] == [3.0,2.0,1.0]


def test_update_model_missing_params(server):
    srv, sf, cf, cf2 = server
    conn = DummyConn()
    # no user and weights
    srv.process_request({"cmd":"update_model"}, conn, sf, cf, cf2)
    assert b'"status":"error"' in conn.data and b'"msg":"user,weights required"' in conn.data
    conn.data = b""
    # missing weights
    srv.process_request({"cmd":"update_model","user":"bob"}, conn, sf, cf, cf2)
    assert b'"msg":"user,weights required"' in conn.data
    conn.data = b""
    # missing user
    srv.process_request({"cmd":"update_model","weights":[1,2,3]}, conn, sf, cf, cf2)
    assert b'"msg":"user,weights required"' in conn.data


@pytest.fixture
def tmp_server_files(tmp_path):
    stock_file = tmp_path / "stocks.json"
    clients_file = tmp_path / "clients.json"
    # seed a couple symbols
    stock_file.write_text(json.dumps({"AAPL": 100.0, "TSLA": 200.0}))
    clients_file.write_text(json.dumps({}))
    return str(stock_file), str(clients_file)

def test_server_register_and_persistence(tmp_server_files):
    stock_file, clients_file = tmp_server_files
    srv = TradingServer("h", 0, stock_file, "", clients_file)
    srv.load_state()
    conn = DummyConn()
    srv.process_request({"cmd":"register","user":"alice"}, conn, None, None, clients_file)
    assert b'"status":"ok"' in conn.data
    clients = load_json(clients_file, {})
    assert "alice" in clients

def test_server_list_symbols(tmp_server_files):
    stock_file, clients_file = tmp_server_files
    srv = TradingServer("h", 0, stock_file, "", clients_file)
    srv.load_state()
    conn = DummyConn()
    srv.process_request({"cmd":"list_symbols"}, conn, None, None, None)
    resp = json.loads(conn.data.decode())
    assert set(resp["symbols"]) == {"AAPL","TSLA"}

def test_server_buy_and_get_portfolio(tmp_server_files):
    stock_file, clients_file = tmp_server_files
    srv = TradingServer("h", 0, stock_file, "", clients_file)
    srv.load_state()
    # ensure user exists
    conn = DummyConn()
    srv.process_request({"cmd":"register","user":"bob"}, conn, None, None, clients_file)

    # buy 5 shares of AAPL
    conn = DummyConn()
    srv.process_request({"cmd":"buy","user":"bob","symbol":"AAPL","qty":5}, conn, None, None, clients_file)
    resp = json.loads(conn.data.decode())
    assert resp["status"]=="ok"
    # now get portfolio
    conn = DummyConn()
    srv.process_request({"cmd":"get_portfolio","user":"bob"}, conn, stock_file, currency_file, clients_file)
    resp = json.loads(conn.data.decode())
    assert resp["portfolio"]["AAPL"][0] == 5

def test_server_model_rpc(tmp_server_files):
    stock_file, clients_file = tmp_server_files
    srv = TradingServer("h",0,stock_file,"",clients_file)
    # get_global_model
    conn = DummyConn()
    srv.process_request({"cmd":"get_global_model"}, conn, None, None, None)
    resp = json.loads(conn.data.decode())
    assert resp["status"]=="ok" and isinstance(resp["weights"], list)
    # update_model from two users
    conn = DummyConn()
    srv.process_request({"cmd":"update_model","user":"u1","weights":[1,2,3]}, conn, None, None, None)
    conn = DummyConn()
    srv.process_request({"cmd":"update_model","user":"u2","weights":[1,2,3]}, conn, None, None, None)
    # global_weights should now be the average
    assert srv.global_weights == [1.0,2.0,3.0]

def test_server_unknown_command(tmp_server_files):
    stock_file, clients_file = tmp_server_files
    srv = TradingServer("h",0,stock_file,"",clients_file)
    conn = DummyConn()
    srv.process_request({"cmd":"foobar"}, conn, None, None, None)
    resp = json.loads(conn.data.decode())
    assert resp["status"] == "error"


################### ---------------- TradingClient Tests ----------------###########################


class BreakAfterNSend:
    """Sock stub that raises KeyboardInterrupt after N sendall calls."""
    def __init__(self, n):
        self.sent = []
        self.count = 0
        self.n = n
    def sendall(self, data):
        self.sent.append(data)
        self.count += 1
        if self.count >= self.n:
            raise KeyboardInterrupt
    def recv(self, bufsize):
        return b''

class DummySocket:
    def __init__(self):
        self.closed = False
    def close(self):
        self.closed = True


def test_connect_closes_and_recreates(monkeypatch):
    cli = TradingClient()
    cli.init("example.com", 12345)

    # Create two old sockets and attach them
    old1 = DummySocket()
    old2 = DummySocket()
    cli.sock = old1
    cli.fl_sock = old2

    # Prepare new sockets to be returned by create_connection
    new1 = DummySocket()
    new2 = DummySocket()
    calls = []
    def fake_create_connection(addr):
        calls.append(addr)
        # return new1 on first call, new2 on second
        return new1 if len(calls) == 1 else new2

    # Monkeypatch socket.create_connection
    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    # Call connect()
    cli.connect()

    # Old sockets should have been closed
    assert old1.closed is True
    assert old2.closed is True

    # New sockets should be assigned
    assert cli.sock is new1
    assert cli.fl_sock is new2

    # create_connection called twice with correct address
    assert calls == [("example.com", 12345), ("example.com", 12345)]


def test_autotrade_branching(monkeypatch):
    # 1) Setup client with three symbols: HIGH→sell branch, LOW→buy branch, NONE→hold branch
    cli = TradingClient()
    cli.portfolio = {
        "HIGH": [1, 100.0, 0.3,   0.0],   # pct_change > 0.2 ⇒ sell
        "LOW":  [1, 100.0, -0.05, 0.0],   # -0.1 < pct_change < 0 ⇒ buy
        "NONE": [1, 100.0, 0.0,   0.0],   # else ⇒ hold
    }
    cli.last_prices = { sym: 100.0 for sym in cli.portfolio }

    #stub out federated socket (not used this iteration)
    cli.fl_sock = BreakAfterNSend(n=999)
    monkeypatch.setattr(time, "sleep", lambda _: None)

    #1 get_portfolio + 2 sells + 2 buys = 5 total
    cli.sock = BreakAfterNSend(n=5)

    # stop after one iteration
    with pytest.raises(KeyboardInterrupt):
        cli.autotrade("alice")

    sent = [b.decode().strip() for b in cli.sock.sent]
    assert len(sent) == 5

    objs = [json.loads(s) for s in sent]
    # first call must be get_portfolio
    assert objs[0]["cmd"] == "get_portfolio"
    assert objs[0]["user"] == "alice"

    #SELL HIGH twice
    assert objs[1]["cmd"] == "sell" and objs[1]["symbol"] == "HIGH"
    assert objs[2]["cmd"] == "sell" and objs[2]["symbol"] == "HIGH"

    #BUY LOW twice
    assert objs[3]["cmd"] == "buy" and objs[3]["symbol"] == "LOW"
    assert objs[4]["cmd"] == "buy" and objs[4]["symbol"] == "LOW"

    # ensure NONE symbol never triggered
    assert all(o.get("symbol") != "NONE" for o in objs)

    # last_prices should still get updated for HIGH and LOW
    assert cli.last_prices["HIGH"] == 100.0
    assert cli.last_prices["LOW"]  == 100.0


def test_listen_records_and_prints(capsys):

    # Set up a client with empty state
    cli = TradingClient()
    cli.BUFFER_SIZE = 1024
    cli.portfolio = {}
    cli.last_prices = {}
    cli.local_data = []
    cli.analytics = []

    # Prepare a single portfolio‐update message, then an empty read to trigger sys.exit
    portfolio = {"AAPL": [2, 100.0, 0.0, 10.0]}  # shares, price, pct, profit
    msg = json.dumps({"status": "ok", "portfolio": portfolio}) + "\n"

    class DummySock:
        def __init__(self, responses):
            self._resps = list(responses)
        def recv(self, bufsize):
            return self._resps.pop(0)

    cli.sock = DummySock([msg.encode(), b""])  # first call yields msg, then empty → exit

    # Run listen() and catch the SystemExit
    with pytest.raises(SystemExit):
        cli.listen()

    # After listen, state should have been updated:
    assert cli.portfolio == portfolio
    # record_sample should have been called once for "AAPL"
    assert len(cli.local_data) == 1
    # last_prices updated to the new price
    assert cli.last_prices["AAPL"] == 100.0

    # print_portfolio should have printed the holdings and net profit
    out = capsys.readouterr().out
    assert "Your portfolio:" in out
    assert "AAPL" in out
    assert "Overall net profit" in out
    # analytics list should record the net profit
    assert cli.analytics and cli.analytics[-1] == 10.0


def test_client_compute_and_print_portfolio(capsys):
    cli = TradingClient()
    cli.portfolio = {"X":[1,10,0,5], "Y":[2,20,0,7]}
    # net profit = 5+7 =12
    assert cli.compute_net_profit() == 12
    cli.print_portfolio()
    out = capsys.readouterr().out
    assert "X" in out and "Y" in out
    # analytics should record last net profit
    assert cli.analytics[-1] == 12

def test_client_record_and_train_local_model():
    cli = TradingClient()
    # record two samples
    cli.record_sample(+1, "A", 100, 110, 10)
    cli.record_sample(-1, "A", 110, 100, -10)
    assert len(cli.local_data) == 2
    # train a couple epochs
    orig_w = cli.weights.copy()
    cli.train_local_model(lr=0.01, epochs=2)
    assert len(cli.local_data) == 0
    assert not np.allclose(cli.weights, orig_w)

def test_client_list_symbols_and_rpc(monkeypatch):
    cli = TradingClient()
    cli.init("h",0)
    # stub sock for list_symbols
    cli.sock = DummySock([b'{"symbols":["A","B"]}\n'])
    syms = cli.list_symbols()
    assert syms == ["A","B"]
    # stub fl_sock for model update and pull
    # send_model_update
    cli.fl_sock = DummySock([b'{"status":"ok"}\n'])
    cli.weights = np.array([1,2,3])
    cli.send_model_update("bob")
    # parse what was sent
    sent_msg = cli.fl_sock.sent[0].decode().strip()
    req_obj = json.loads(sent_msg)
    assert req_obj["cmd"] == "update_model"
    assert req_obj["user"] == "bob"
    assert req_obj["weights"] == [1, 2, 3]
    # pull_global_model ignores bad JSON then accepts
    bad = b'{"foo":1}\n'
    good = b'{"weights":[4,5,6]}\n'
    cli.fl_sock = DummySock([bad, good])
    cli.weights = np.zeros(3)
    cli.pull_global_model()
    assert np.allclose(cli.weights, [4,5,6])

def test_client_autotrade_one_iteration(monkeypatch):
    cli = TradingClient()
    cli.portfolio = {"A":[1,100,0.5,5]}
    cli.last_prices = {"A":100}
    cli.weights = np.zeros(3)
    # stub trading socket: first recv delivers portfolio update
    data = [b'{"status":"ok","portfolio":{"A":[1,105,0.5,5]}}\n']
    cli.sock = DummySock(data.copy())
    # stub fl_sock for federated update & model pull
    cli.fl_sock = DummySock([b'{"status":"ok"}\n', b'{"weights":[0,0,0]}\n'])
    # break out after first loop
    monkeypatch.setattr(time, "sleep", lambda x: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        cli.autotrade("alice")
    # ensure at least one sendall happened
    assert len(cli.sock.sent) > 0

    
def test_autotrade_trains_and_sends_update(monkeypatch):
    cli = TradingClient()
    cli.portfolio   = {"A":[1, 100.0, 0.0, 0.0]}
    cli.last_prices = {"A": 100.0}

    sample = (np.array([1.0, 0.0, +1.0]),  0.0)
    cli.local_data = [sample for _ in range(5)]
    cli.sock = DummySock()
    ack = b'{"status":"ok"}\n'
    cli.fl_sock = DummySock(responses=[ack])

    #Monkey‐patch pull_global_model to quit immediately after training
    monkeypatch.setattr(cli, "pull_global_model", lambda: (_ for _ in ()).throw(KeyboardInterrupt))
    monkeypatch.setattr(time, "sleep", lambda _: None)

    #run autotrade
    with pytest.raises(KeyboardInterrupt):
        cli.autotrade("tester")

    #verify local_data was cleared by the training loop
    assert cli.local_data == []
    assert len(cli.fl_sock.sent) == 1

    #parse & inspect the sent JSON
    sent_req = json.loads(cli.fl_sock.sent[0].decode().strip())
    assert sent_req["cmd"]     == "update_model"
    assert sent_req["user"]    == "tester"
    assert isinstance(sent_req["weights"], list)
    # and those weights equal the client’s internal weights at send time
    assert sent_req["weights"] == pytest.approx(cli.weights.tolist())


def test_main_flow_invokes_autotrade(monkeypatch, capsys):
    cli = TradingClient()
    monkeypatch.setattr(cli, "connect", lambda: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "testuser")
    monkeypatch.setattr(cli, "listen", lambda: None)

    #track pull_global_model() calls
    called = {"pulled": False}
    monkeypatch.setattr(cli, "pull_global_model", lambda: called.update(pulled=True))
    monkeypatch.setattr(cli, "autotrade", lambda user: (_ for _ in ()).throw(KeyboardInterrupt))
    cli.sock = DummySock([
        b'{"status":"ok"}\n',
        b'{"status":"ok","portfolio":{}}\n'])

    # FL socket also exists but not used before autotrade
    cli.fl_sock = DummySock([b'{"weights":[0,0,0]}\n'])
    monkeypatch.setattr(time, "sleep", lambda _: None)
    with pytest.raises(KeyboardInterrupt):
        cli.main()

    #check that register and get_portfolio were sent
    assert len(cli.sock.sent) >= 2
    reg = json.loads(cli.sock.sent[0].decode())
    assert reg["cmd"] == "register" and reg["user"] == "testuser"
    gp = json.loads(cli.sock.sent[1].decode())
    assert gp["cmd"] == "get_portfolio" and gp["user"] == "testuser"

    #commands menu should have been printed
    out = capsys.readouterr().out
    assert "Commands:" in out
    assert "buy SYMBOL QTY" in out
    assert called["pulled"] is True


def test_pull_global_model_skips_bad_json_and_updates_weights():
    cli = TradingClient()
    cli.BUFFER_SIZE = 1024

    # stub fl_sock to first return invalid JSON, then a valid weights reply
    bad = b'invalid json\n'
    good = b'{"weights":[9,8,7]}\n'
    cli.fl_sock = DummySock([bad, good])

    # start from zero weights
    cli.weights = np.zeros(3)

    # call pull_global_model; it should loop once on bad JSON then succeed
    cli.pull_global_model()

    # verify that weights were updated to [9,8,7]
    assert np.allclose(cli.weights, [9, 8, 7])

    # verify that exactly one get_global_model request was sent
    assert len(cli.fl_sock.sent) == 1
    req_obj = json.loads(cli.fl_sock.sent[0].decode().strip())
    assert req_obj == {"cmd": "get_global_model"}



######################STOCKPRICE MANAGER SCRIPT TESTS#########################



class DummySched:
    def __init__(self):
        self.enter_calls = []
    def enter(self, delay, priority, func, args):
        self.enter_calls.append((delay, priority, func, args))
    def run(self):
        # don’t actually block
        return


def test_simulate_prices(tmp_path, monkeypatch, capsys):
    #stocks file with two symbols
    f = tmp_path / "stocks.txt"
    orig = {"AAA": 100.0, "BBB": 200.0}
    f.write_text(json.dumps(orig))
    monkeypatch.setattr(stockpricemanager, "STOCK_FILE", str(f))
    monkeypatch.setattr(stockpricemanager.random, "gauss", lambda mu, sigma: 0.0)
    monkeypatch.setattr(stockpricemanager.time, "ctime", lambda: "NOW")
    sc = DummySched()
    stockpricemanager.simulate_prices(sc)

    #check that file was overwritten with the correct GBM step
    updated = json.loads(f.read_text())
    factor = math.exp((stockpricemanager.MU - 0.5 * stockpricemanager.SIGMA**2) * stockpricemanager.DT)
    assert updated["AAA"] == round(100.0 * factor, 2)
    assert updated["BBB"] == round(200.0 * factor, 2)
    out = capsys.readouterr().out
    assert "[NOW] Updated prices:" in out
    # ensure the dict appears
    assert "AAA" in out and "BBB" in out
    assert sc.enter_calls == [(stockpricemanager.UPDATE_INTERVAL, 1, stockpricemanager.simulate_prices, (sc,))]


def test_main_schedules_and_runs(monkeypatch, capsys):
    monkeypatch.setattr(stockpricemanager.sched, "scheduler", lambda tfunc, sf: DummySched())
    stockpricemanager.main()
    out = capsys.readouterr().out
    assert "Stock Price Manager starting..." in out


def test_main_enter_called(monkeypatch):
    #use a container to capture the instance
    created = {}
    def fake_scheduler(timefunc, sleepfunc):
        s = DummySched()
        created['inst'] = s
        return s

    monkeypatch.setattr(stockpricemanager.sched, "scheduler", fake_scheduler)
    #we only care about enter(), run() is no-op
    stockpricemanager.main()

    #after main, the scheduler instance should have one enter call
    s = created['inst']
    assert len(s.enter_calls) == 1
    delay, priority, func, args = s.enter_calls[0]
    assert delay == 0
    assert priority == 1
    #scheduled function should be simulate_prices, with the scheduler as argument
    assert func is stockpricemanager.simulate_prices
    assert args == (s,)