#to run: pytest --cov=. --cov-report=term-missing unittests.py
import pytest
import json
import math
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

    #run listen() and catch the SystemExit and update teh portfolio
    with pytest.raises(SystemExit):
        cli.listen()

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


def test_plot_analytics_empty(capsys, monkeypatch):
    cli = TradingClient()
    cli.analytics = []  # no data

    # Spy on plt.figure to ensure it never gets called
    called = {"figure": False}
    monkeypatch.setattr(plt, "figure", lambda *args, **kwargs: called.update(figure=True))

    cli.plot_analytics("alice")
    out = capsys.readouterr().out
    assert "No data to plot." in out
    assert not called["figure"]  # plot code never ran


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