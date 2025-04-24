# rl_env.py
# Wraps the existing trading_client socket logic in a gym-like environment API
import json
import threading
from client import TradingClient

class TradingEnv:
    def __init__(self, host: str, port: int, user: str, max_steps: int = 100, qty_options: list = None):
        self.client = TradingClient()
        self.user = user
        self.max_steps = max_steps
        self.current_step = 0
        self.last_net = 0.0

    def reset(self, qty_options: list = None):
        # Register or reconnect as the user
        self.client.connect()
        self.symbols = self.client.list_symbols()    # e.g. ["AAPL","TSLA","GOOG",…]
        self.qty_options = qty_options or [1,5,10]   # you can parameterize this too
        self.action_dim = len(self.symbols) * 2 * len(self.qty_options)
        self.client.register(self.user)
        obs = self.client.get_portfolio(self.user)
        self.last_net = obs.get("total_profit", 0.0)
        self.current_step = 0
        return self._encode(obs)

    def step(self, action: dict):
        # action = {"type": "buy"/"sell", "symbol": str, "qty": int}
        cmd = {
            "cmd": action["type"],
            "user": self.user,
            "symbol": action["symbol"],
            "qty": action["qty"]
        }
        self.client.trade(cmd)
        obs = self.client.get_portfolio(self.user)
        net = obs.get("total_profit", 0.0)
        reward = net - self.last_net
        self.last_net = net
        self.current_step += 1
        done = self.current_step >= self.max_steps
        return self._encode(obs), reward, done, {}

    def _encode(self, obs: dict):
        # Convert raw obs into a feature vector (e.g. price changes + holdings)
        # Placeholder example: [net, unrealized, realized]
        return [
            obs.get("total_profit", 0.0),
            obs.get("unrealized_profit", 0.0),
            obs.get("realized_profit", 0.0)
        ]