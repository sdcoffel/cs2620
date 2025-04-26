# all tests done locally under 'localhost'
import pytest
import socket
import threading
import json
import time
import math
import stockpricemanager
from server import TradingServer

"""This integration test suite is designed to test the TradingServer class and its methods.
It includes tests for normal trading flows, federated learning flows, and the stock price manager's functionality.
"""
class TestTradingServer(TradingServer):
    def serve_forever(self, max_connections=1):
        self.load_state()
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv_sock.bind((self.host, self.port))
        srv_sock.listen()
        conns = 0
        try:
            while conns < max_connections:
                conn, addr = srv_sock.accept()
                self.handle_client(conn, addr)
                conns += 1
        finally:
            self.save_state()
            srv_sock.close()

@pytest.fixture
def server_fixture(tmp_path):
    #temporary data files
    stock_file   = tmp_path/"stocks.txt"
    currency_file= tmp_path/"currency.txt"
    clients_file = tmp_path/"clients.txt"
    #stock prices
    stock_file.write_text(json.dumps({"AAPL":100.0, "TSLA":200.0}))
    currency_file.write_text(json.dumps({}))
    clients_file.write_text(json.dumps({}))
  
    sock = socket.socket()
    sock.bind(("localhost", 0))
    port = sock.getsockname()[1]
    sock.close()
    #start server
    srv = TestTradingServer("localhost", port,
                            str(stock_file), str(currency_file), str(clients_file))
    thread = threading.Thread(target=srv.serve_forever, kwargs={"max_connections":20}, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield srv, "localhost", port, str(stock_file), str(currency_file), str(clients_file)
    thread.join(timeout=1)

def test_normal_trading_flow(server_fixture):
    srv, host, port, _, _, clients_file = server_fixture
    #client side: open a raw socket
    sock = socket.create_connection((host, port))
  
    sock.sendall((json.dumps({"cmd":"register","user":"alice"})+"\n").encode())
    resp = json.loads(sock.recv(1024).decode())
    assert resp["status"] == "ok"
   
    sock.sendall((json.dumps({"cmd":"list_symbols"})+"\n").encode())
    resp = json.loads(sock.recv(1024).decode())
    assert set(resp["symbols"]) == {"AAPL","TSLA"}

    #buy 10 AAPL
    sock.sendall((json.dumps({"cmd":"buy","user":"alice","symbol":"AAPL","qty":10})+"\n").encode())
    resp = json.loads(sock.recv(1024).decode())
    assert resp["status"] == "ok"
   
    sock.sendall((json.dumps({"cmd":"get_portfolio","user":"alice"})+"\n").encode())
    resp = json.loads(sock.recv(1024).decode())
    assert resp["portfolio"]["AAPL"][0] == 10
    #sell 5 AAPL
    sock.sendall((json.dumps({"cmd":"sell","user":"alice","symbol":"AAPL","qty":5})+"\n").encode())
    resp = json.loads(sock.recv(1024).decode())
    assert resp["status"] == "ok"
    
    sock.sendall((json.dumps({"cmd":"get_portfolio","user":"alice"})+"\n").encode())
    resp = json.loads(sock.recv(1024).decode())
    assert resp["portfolio"]["AAPL"][0] == 5
    sock.close()

def test_federated_learning_flow(server_fixture):
    srv, host, port, _, _, _ = server_fixture
    #client connects
    sock = socket.create_connection((host, port))
    sock.sendall((json.dumps({"cmd":"register","user":"u1"})+"\n").encode())
    sock.recv(1024)
    #update model with [1,1,1]
    sock.sendall((json.dumps({"cmd":"update_model","user":"u1","weights":[1,1,1]})+"\n").encode())
    resp1 = json.loads(sock.recv(1024).decode())
    assert resp1["status"] == "ok"
    #client can pull the global model
    sock.sendall((json.dumps({"cmd":"get_global_model"})+"\n").encode())
    global_model = json.loads(sock.recv(1024).decode())["weights"]
    #make sure that the global model is the same as the one sent by client 
    assert global_model == [1.0, 1.0, 1.0]
    sock.close()


class DummySched:
    def __init__(self):
        self.enter_calls = []
    def enter(self, delay, priority, func, args):
        self.enter_calls.append((delay, priority, func, args))

class DummyConn:
    def __init__(self):
        self.data = b""
    def sendall(self, b: bytes):
        self.data += b

def test_stockprice_manager_updates_and_server_reads(tmp_path, monkeypatch):
    stock_file    = tmp_path / "stocks.txt"
    clients_file  = tmp_path / "clients.txt"
    currency_file = tmp_path / "currency.txt"

    initial_price = 100.0
    stock_file.write_text(json.dumps({"XYZ": initial_price}))
    clients_file.write_text(json.dumps({"tester": {"XYZ": [5, initial_price, 0, 0]}}))
    currency_file.write_text(json.dumps({}))
    monkeypatch.setattr(stockpricemanager.random, "gauss", lambda mu, sigma: 0.0)
    monkeypatch.setattr(stockpricemanager.time,   "ctime", lambda: "NOW")

    #run one simulate_prices
    sched = DummySched()
    stockpricemanager.simulate_prices(sched)

    #check file was updated correctly
    updated = json.loads(stock_file.read_text())
    factor = math.exp((stockpricemanager.MU - 0.5*stockpricemanager.SIGMA**2)*stockpricemanager.DT)
    expected_price = round(initial_price * factor, 2)
    assert updated["XYZ"] == expected_price
    assert sched.enter_calls == [(stockpricemanager.UPDATE_INTERVAL, 1, stockpricemanager.simulate_prices, (sched,))]

    #spin up a server pointed at these files
    srv = TradingServer(
        host="localhost", port=0,
        stock_file=str(stock_file),
        currency_file=str(currency_file),
        clients_file=str(clients_file))
    srv.load_state()

    conn = DummyConn()
    srv.process_request(
        {"cmd": "get_portfolio", "user": "tester"},
        conn,
        str(stock_file),
        str(currency_file),
        str(clients_file))
    resp = json.loads(conn.data.decode())
    assert resp["status"] == "ok"
    port = resp["portfolio"]["XYZ"]

    #validate returned price and unrealized P&L
    shares, price, pct, unreal = port
    assert price == expected_price
    expected_unreal = round(5 * (expected_price - initial_price), 2)
    assert unreal == expected_unreal
