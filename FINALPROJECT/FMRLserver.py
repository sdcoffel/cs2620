#this is the federated server: serves global model, aggregates client deltas with Fed-Adam
from flask import Flask, request, jsonify
import torch
import threading
from model import PolicyNet
from client import TradingClient

app = Flask(__name__)
lock = threading.Lock()

#Fed-Adam hyperparameters
BETA1 = 0.9
BETA2 = 0.999
ETA = 1e-3
EPS = 1e-8

#initialize global model and optimizer state
trade_client = TradingClient()
trade_client.init("localhost", 50004)
trade_client.connect()
symbols     = trade_client.list_symbols()       #list of stocks the client owns 
qty_options = [1,5,10,20]                      #number of shares to buy/sell - need to make this dynamic

#network dims:
obs_dim   = 3                 # rl_env._encode() → 3 values
n_symbols = len(symbols)
n_qtys    = len(qty_options)


#load in the global model
global_model = PolicyNet(obs_dim, n_symbols, n_qtys)
global_weights = global_model.state_dict()
first_moment = {k: torch.zeros_like(v) for k, v in global_weights.items()}
second_moment = {k: torch.zeros_like(v) for k, v in global_weights.items()}
timestep = 0


def serialize_state_dict(state_dict):
    """Convert a PyTorch state_dict into JSON-serializable lists."""
    return {k: v.cpu().numpy().tolist() for k, v in state_dict.items()}


def deserialize_state_dict(data):
    """Convert JSON lists back into a PyTorch state_dict."""
    return {k: torch.tensor(v) for k, v in data.items()}


@app.route('/get_weights', methods=['GET'])
def get_weights():
    with lock:
        return jsonify(serialize_state_dict(global_weights))


@app.route('/submit_delta', methods=['POST'])
def submit_delta():
    """
    Receive a single client's Δθ and perform one Fed-Adam aggregation step.
    """
    global global_weights, first_moment, second_moment, timestep
    payload = request.get_json(force=True)
    delta = deserialize_state_dict(payload['delta'])

    with lock:
        timestep += 1
        #single-client average == delta
        for name in global_weights:
            #update biased moments
            first_moment[name] = BETA1 * first_moment[name] + (1 - BETA1) * delta[name]
            second_moment[name] = BETA2 * second_moment[name] + (1 - BETA2) * (delta[name] * delta[name])
            #recompute bias-corrected moments
            m_hat = first_moment[name] / (1 - BETA1**timestep)
            v_hat = second_moment[name] / (1 - BETA2**timestep)
            #update global parameters
            global_weights[name] += ETA * m_hat / (torch.sqrt(v_hat) + EPS)

    return jsonify(status='ok')


if __name__ == '__main__':
    #runs on port 50005 by default - needs to be separate from server.py
    app.run(host='localhost', port=50005)