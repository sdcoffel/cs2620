#to run: pytest --cov=. --cov-report=term-missing unittests.py
import pytest
import json
import sys
import math
import time
import numpy as np
import socket
import matplotlib.pyplot as plt
from server import TradingServer, load_json, save_json
from client import TradingClient
import stockpricemanager

"""These unittests are designed to test the TradingServer and TradingClient classes and all of their associated methods.
They include tests for their functions, client/server communication, and training flows.
These cover server.py, client.py, stockpricemanager.py, and graphs.py (TO BE ADDED).
"""

#warnings schmarnings. pytest skill issue. update ur pytest if it bothers you that much. 
clients_file='clients.txt'
stock_file='stocks.txt'
currency_file='currencies.txt'


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


@pytest.fixture
def setup_server(tmp_path):
    # prepare stock & client files
    stock_file    = tmp_path / "stocks.json"
    clients_file  = tmp_path / "clients.json"
    currency_file = tmp_path / "currency.json"
    # one symbol at $100
    stock_file.write_text(json.dumps({"AAPL": 100.0}))
    # user 'bob' holds 5 shares @ $90 basis
    clients_file.write_text(json.dumps({"bob": {"AAPL": [5, 90.0, 0.0, 0.0]}}))
    currency_file.write_text(json.dumps({}))
    srv = TradingServer(
        host="h", port=0,
        stock_file=str(stock_file),
        currency_file=str(currency_file),
        clients_file=str(clients_file)
    )
    srv.load_state()
    return srv, str(stock_file), str(currency_file), str(clients_file)


def test_sell_not_enough_shares(setup_server):
    srv, sf, cf, cuf = setup_server
    conn = DummyConn()
    # attempt to sell more (10) than bob holds (5)
    srv.process_request(
        {"cmd":"sell","user":"bob","symbol":"AAPL","qty":10},
        conn, sf, cf, cuf
    )
    # should return the 'not enough shares' error
    assert b'not enough shares' in conn.data


def test_sell_partial_updates_realized_and_shares(setup_server):
    srv, sf, cf, cuf = setup_server
    conn = DummyConn()
    # sell 3 of the 5 shares
    srv.process_request(
        {"cmd":"sell","user":"bob","symbol":"AAPL","qty":3},
        conn, sf, cf, cuf)
    # parse response
    resp = json.loads(conn.data.decode())
    assert resp["status"] == "ok"
    port = resp["portfolio"]
    # new_shares = 5 - 3 = 2
    assert port["AAPL"][0] == 2
    # realized gain = 3 * (current_price - basis) = 3 * (100 - 90) = 30
    # stored in index 2
    assert math.isclose(port["AAPL"][2], round(30.0, 2))
    # basis should be updated to current_price
    assert port["AAPL"][1] == 100.0


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

class DummySock:
    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self.sent = []
    def recv(self, bufsize):
        return self._responses.pop(0) if self._responses else b''
    def sendall(self, data):
        self.sent.append(data)
    def close(self):
        pass

#break out of infinite loops by raising in time.sleep
class SleepBreaker:
    def __init__(self, after=1):
        self.count = 0
        self.after = after
    def __call__(self, sec):
        self.count += 1
        if self.count >= self.after:
            raise KeyboardInterrupt

class DummySocket:
    def __init__(self):
        self.closed = False
    def close(self):
        self.closed = True

#for some of the ml tests
class DummySock:
    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self.sent = []
    def recv(self, bufsize):
        return self._responses.pop(0) if self._responses else b''
    def sendall(self, data):
        self.sent.append(data)
    def close(self):
        pass


def test_init_defaults():
    cli = TradingClient()
    # defaults
    assert cli.host is None
    assert cli.port is None
    assert cli.BUFFER_SIZE == 2048
    assert isinstance(cli.weights, np.ndarray) and np.all(cli.weights == 0)
    assert cli.local_data == []
    assert cli.analytics == []
    assert cli.loss_history == []
    assert cli.accuracy == []


def test_init_sets_values():
    cli = TradingClient()
    cli.init("h", 9999, buffer_size=123)
    assert cli.host == "h"
    assert cli.port == 9999
    assert cli.BUFFER_SIZE == 123


def test_connect_closes_old_sockets_and_creates_new(monkeypatch):
    cli = TradingClient()
    cli.init("example.com", 1234)

    #dummy existing sockets
    old_sock1 = DummySocket()
    old_sock2 = DummySocket()
    cli.sock = old_sock1
    cli.fl_sock = old_sock2

    #prep two new DummySockets to be returned by create_connection
    new1 = DummySocket()
    new2 = DummySocket()
    calls = []
    def fake_create_connection(addr):
        calls.append(addr)
        # Return new1 on first call, new2 on second
        return new1 if len(calls) == 1 else new2

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    cli.connect()

    #old sockets were closed
    assert old_sock1.closed is True
    assert old_sock2.closed is True

    #cli.sock and cli.fl_sock now point to the new sockets
    assert cli.sock is new1
    assert cli.fl_sock is new2

    #create_connection was called twice with correct address
    assert calls == [("example.com", 1234), ("example.com", 1234)]


def test_list_symbols_and_error(monkeypatch):
    cli = TradingClient()
    # happy path
    cli.sock = DummySock([b'{"symbols":["X","Y"]}\n'])
    syms = cli.list_symbols()
    assert syms == ["X","Y"]

    # empty or malformed resp
    cli.sock = DummySock([b'{}\n'])
    assert cli.list_symbols() == []


def test_compute_net_profit_various():
    cli = TradingClient()
    # empty
    cli.portfolio = {}
    assert cli.compute_net_profit() == 0.0
    # positive only
    cli.portfolio = {"A":[1,0,0, 5]}
    assert cli.compute_net_profit() == 5
    # mixed
    cli.portfolio = {"A":[0,0,0,-2],"B":[0,0,0,3]}
    assert cli.compute_net_profit() == 1


def test_print_portfolio_and_return(capsys):
    cli = TradingClient()
    # empty
    cli.portfolio = {}
    net = cli.print_portfolio()
    out = capsys.readouterr().out
    assert "Your portfolio:" in out
    assert "Overall net profit:    $0.00" in out
    assert net == 0.0

    # multi
    cli.portfolio = {
        "A":[1,100,5.0,10.0],
        "B":[2,200,-3.0,-6.0]
    }
    net = cli.print_portfolio()
    out = capsys.readouterr().out
    assert "A: 1 @ $100.00" in out
    assert "Δ +5.0%" in out
    assert "P&L $10.00" in out
    assert "B: 2 @ $200.00" in out
    assert "Δ -3.0%" in out
    assert "P&L $-6.00" in out
    # net = 10 + (-6) = 4.0
    assert net == pytest.approx(4.0)

def test_record_sample_appends():
    cli = TradingClient()
    cli.local_data = []
    cli.record_sample(1, "S", 10.0, 12.5, 2.5)
    assert len(cli.local_data) == 1
    x, y = cli.local_data[0]
    assert pytest.approx(x.tolist()) == [1.0, 2.5, 1]
    assert y == 2.5


def test_send_model_update_and_recv():
    cli = TradingClient()
    cli.weights = np.array([1,2,3])
    cli.fl_sock = DummySock([b'{"status":"ok"}\n'])
    cli.send_model_update("u1")
    assert len(cli.fl_sock.sent) == 1
    obj = json.loads(cli.fl_sock.sent[0].decode())
    assert obj == {"cmd":"update_model","user":"u1","weights":[1,2,3]}


def test_autotrade_training_and_federated_update(monkeypatch):
    cli = TradingClient()
    cli.portfolio = {"TICK": [1, 100.0, 0.0, 0.0]}

    #use x vectors that give pred=0 so we test the training loss & accuracy logic
    sample = (np.array([1.0, 0.0, 0.0]), 2.0)
    cli.local_data = [sample]*5
    monkeypatch.setattr(cli, "pull_global_model", lambda: None)
    monkeypatch.setattr(cli, "print_portfolio", lambda: 42.0)
    cli.sock = DummySock()

    # respond with a dummy OK so send_model_update can proceed
    cli.fl_sock = DummySock([b'{"status":"ok"}\n'])

    #first sleep is for fetching portfolio, second sleep(1) is at end
    sleeper = SleepBreaker(after=2)
    monkeypatch.setattr(time, "sleep", sleeper)
    with pytest.raises(KeyboardInterrupt):
        cli.autotrade("user1")

    #should have consumed 5 samples → loss_history & accuracy & analytics length == 5
    assert len(cli.loss_history) == 5
    assert len(cli.accuracy)     == 5
    assert len(cli.analytics)    == 5
    assert any(b'get_portfolio' in msg for msg in cli.sock.sent)
    assert len(cli.fl_sock.sent) == 1
    payload = json.loads(cli.fl_sock.sent[0].decode().strip())
    assert payload["cmd"] == "update_model"
    assert payload["user"] == "user1"

    # weights should have been updated in the training loop
    assert isinstance(payload["weights"], list)


def test_pull_global_model_skips_and_updates(monkeypatch):
    cli = TradingClient()
    # two responses: bad, then good
    cli.fl_sock = DummySock([b'notjson\n', b'{"weights":[5,6,7]}\n'])
    # capture stdout
    cli.BUFFER_SIZE = 1024
    cli.pull_global_model()
    assert np.all(cli.weights == np.array([5,6,7]))


def test_listen_updates_and_exit(monkeypatch):
    cli = TradingClient()
    # first valid, then empty to exit
    portfolio = {"Z":[1, 10.0, 0.0, 1.0]}
    msg = json.dumps({"status":"ok","portfolio":portfolio}) + "\n"
    cli.sock = DummySock([msg.encode(), b''])
    # stub record_sample & exit
    calls = []
    monkeypatch.setattr(cli, "record_sample", lambda *args: calls.append(args))
    monkeypatch.setattr(sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit()))
    with pytest.raises(SystemExit):
        cli.listen()
    assert cli.portfolio == portfolio
    assert calls  # record_sample called


def test_fetch_portfolio_success_and_fail():
    cli = TradingClient()
    # success
    cli.sock = DummySock([b'{"status":"ok","portfolio":{"X":[1,2,3,4]}}\n'])
    res = cli.fetch_portfolio("u")
    assert res == {"X":[1,2,3,4]}
    # failure
    cli.sock = DummySock([b'{"status":"error","msg":"bad"}\n'])
    with pytest.raises(RuntimeError):
        cli.fetch_portfolio("u")


def test_autotrade_one_iteration(monkeypatch):
    cli = TradingClient()
    # setup minimal portfolio and data
    cli.portfolio = {"T":[1, 100.0, 0.0, 0.0]}
    cli.weights = np.array([0, 1, 0])  # pred = Δp
    # give 5 samples so training loop runs
    cli.local_data = [(np.array([1.0, 0.0, 0]), 0.0)]*5
    # stub pull_global_model no-op
    monkeypatch.setattr(cli, "pull_global_model", lambda: None)
    # stub sock responses: get_portfolio ack then further recv not used
    cli.sock = DummySock([b'{"status":"ok","portfolio":{"T":[1,101.0,1.0,1.0]}}\n'])
    # fl_sock
    cli.fl_sock = DummySock([b'{"status":"ok"}\n'])
    # stub print_portfolio so analytics updated
    monkeypatch.setattr(cli, "print_portfolio", lambda: 123.0)
    # break after first sleep
    monkeypatch.setattr(time, "sleep", SleepBreaker(after=1))
    with pytest.raises(KeyboardInterrupt):
        cli.autotrade("u")

    # should have sent get_portfolio + buy+sell actions + update_model
    assert any(b'get_portfolio' in s for s in cli.sock.sent)


def make_plot_test(func_name, args, expected_calls):
    """Helper to generate plot tests."""
    def _test(monkeypatch):
        cli = TradingClient()
        # populate relevant history
        if func_name=="plot_analytics":
            cli.analytics = [1,2,3,4]
        elif func_name=="plot_loss":
            cli.loss_history = [0.1,0.2]
        else:
            cli.accuracy = [0.5,0.75,1.0]
        calls = {'figure':0,'plot':0,'title':0,'xlabel':0,'ylabel':0,'grid':0,'legend':0,'show':0,'ylim':0}
        monkeypatch.setattr(plt, 'figure',      lambda *a,**k: calls.__setitem__('figure',calls['figure']+1))
        monkeypatch.setattr(plt, 'plot',        lambda *a,**k: calls.__setitem__('plot',calls['plot']+1))
        monkeypatch.setattr(plt, 'title',       lambda *a,**k: calls.__setitem__('title',calls['title']+1))
        monkeypatch.setattr(plt, 'xlabel',      lambda *a,**k: calls.__setitem__('xlabel',calls['xlabel']+1))
        monkeypatch.setattr(plt, 'ylabel',      lambda *a,**k: calls.__setitem__('ylabel',calls['ylabel']+1))
        monkeypatch.setattr(plt, 'grid',        lambda *a,**k: calls.__setitem__('grid',calls['grid']+1))
        monkeypatch.setattr(plt, 'legend',      lambda *a,**k: calls.__setitem__('legend',calls['legend']+1))
        monkeypatch.setattr(plt, 'show',        lambda *a,**k: calls.__setitem__('show',calls['show']+1))
        if func_name=="plot_accuracy":
            monkeypatch.setattr(plt, 'ylim',   lambda *a,**k: calls.__setitem__('ylim',calls['ylim']+1))

        getattr(cli, func_name)(*args)
        # assert at least the expected minimal calls happened
        for k,v in expected_calls.items():
            assert calls[k] >= v, f"{func_name} expected at least {v} calls to {k}, got {calls[k]}"
    return _test


# plot_analytics test
test_plot_analytics = make_plot_test(
    "plot_analytics", ["user"], 
    {"figure":1,"plot":1,"title":1,"xlabel":1,"ylabel":1,"grid":1,"legend":1,"show":1})
# plot_loss test
test_plot_loss = make_plot_test(
    "plot_loss", ["user"], 
    {"figure":1,"plot":1,"title":1,"xlabel":1,"ylabel":1,"grid":1,"legend":1,"show":1})
# plot_accuracy test
test_plot_accuracy = make_plot_test(
    "plot_accuracy", ["user"], 
    {"figure":1,"plot":1,"title":1,"xlabel":1,"ylabel":1,"grid":1,"legend":1,"show":1,"ylim":1})

# parameterize them so pytest collects
@pytest.mark.usefixtures("test_plot_analytics", "test_plot_loss", "test_plot_accuracy")
class TestPlots:
    pass

def test_main_full_flow(monkeypatch, capsys):
    cli = TradingClient()
    cli.init("h", 1)
    # stub connect
    monkeypatch.setattr(cli, "connect", lambda: None)
    # stub input
    monkeypatch.setattr('builtins.input', lambda prompt="": "me")
    # prepare register response including portfolio
    cli.sock = DummySock([json.dumps({"status":"ok","portfolio":{"Z":[0,1,0,0]}}).encode()])
    # prepare pull_global_model
    monkeypatch.setattr(cli, "pull_global_model", lambda: setattr(cli, 'weights', np.array([0,0,0])))
    # stub listen thread to no-op
    monkeypatch.setattr(cli, "listen", lambda: None)
    # stub autotrade to raise
    monkeypatch.setattr(cli, "autotrade", lambda user: (_ for _ in ()).throw(KeyboardInterrupt))
    # stub plot methods to record
    calls = {}
    for name in ("plot_analytics","plot_loss","plot_accuracy"):
        monkeypatch.setattr(cli, name, lambda user, n=name: calls.setdefault(n,0) or calls.__setitem__(n,1))
    # run main
    #with pytest.raises(KeyboardInterrupt):
    cli.main()
    out = capsys.readouterr().out
    assert "Starting trading session for me" in out
    # ensure plot methods called
    assert calls["plot_analytics"] == 1
    assert calls["plot_loss"]      == 1
    assert calls["plot_accuracy"]  == 1


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
    assert "Stock Price Manager firing up" in out


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