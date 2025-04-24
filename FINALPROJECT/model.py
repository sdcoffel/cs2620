# model.py
"""
Defines the neural network architecture (PolicyNet) used by the federated RL client and server.
Replace OBSERVATION_DIM and ACTION_DIM with your actual environment dimensions.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

#these must match TRADINGENV
OBSERVATION_DIM = 3    # number of features returned by rl_env._encode()
ACTION_DIM = 4         # e.g., number of discrete actions (buy/sell/hold,quit for each symbol)

class PolicyNet(nn.Module):
    def __init__(self, obs_dim, n_symbols, n_qtys):
        super().__init__()
        hidden = 64
        self.fc1 = nn.Linear(obs_dim, hidden)
        self.fc2 = nn.Linear(hidden, hidden)
        # three heads:
        self.symbol_head   = nn.Linear(hidden, n_symbols)
        self.direction_head= nn.Linear(hidden, 2)       # buy vs sell
        self.qty_head      = nn.Linear(hidden, n_qtys)
        self.value_head    = nn.Linear(hidden, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return (
            self.symbol_head(x),
            self.direction_head(x),
            self.qty_head(x),
            self.value_head(x)
        )