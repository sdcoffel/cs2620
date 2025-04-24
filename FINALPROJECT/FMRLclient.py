# this is the federated Meta-RL client: pulls global model, adapts locally via PPO+MAML, and pushes updates.
import requests
import torch
import numpy as np
from model import PolicyNet       # Your network definition
from RLenvironment import TradingEnv      # The Gym-style wrapper
from torch.optim import SGD
from torch.distributions import Categorical

#address of the federated server
SERVER_URL = 'http://localhost:50005'

#hyperparams
INNER_LR = 0.1     # α: learning rate for inner (MAML) step
LOCAL_LR = 0.001   # β: learning rate for local PPO update
INNER_STEPS = 1    # T: number of inner adaptation steps


def get_global_weights():
    """Fetch the current global_weights from the federated server."""
    resp = requests.get(f"{SERVER_URL}/get_weights")
    resp.raise_for_status()
    data = resp.json()
    # deserialize from lists back to tensors
    return {k: torch.tensor(v) for k, v in data.items()}


def submit_delta(delta):
    """Send the client-side parameter delta back to the federated server."""
    # convert tensors to lists for JSON
    payload = {'delta': {k: v.cpu().numpy().tolist() for k, v in delta.items()}}
    resp = requests.post(f"{SERVER_URL}/submit_delta", json=payload)
    resp.raise_for_status()
    return resp.json()


def ppo_clipped_loss(policy, obs_batch, act_batch, old_logp_batch, adv_batch, clip_eps=0.2):
    logits, values = policy(obs_batch)
    dist = Categorical(logits=logits)
    logps = dist.log_prob(act_batch)
    ratios = torch.exp(logps - old_logp_batch)
    clipped = torch.clamp(ratios, 1-clip_eps, 1+clip_eps) * adv_batch
    loss = -torch.mean(torch.min(ratios * adv_batch, clipped))
    #add a value-function loss and an entropy bonus here?
    return loss


def compute_gae(rewards, values, next_value, gamma=0.99, lam=0.95):
    """
    Compute GAE advantages.

    Args:
      rewards      : list of rewards [r0, r1, …, r_{T-1}]
      values       : list of state-values [V(s0), V(s1), …, V(s_{T-1})]
      next_value   : V(s_T), the value estimate of the state _after_ the last reward
      gamma        : discount factor
      lam          : GAE lambda

    Returns:
      advantages   : torch.Tensor of shape (T,) with Â_0 … Â_{T-1}
    """
    T = len(rewards)
    # append V(s_T) so that values[t+1] is valid up to t=T-1
    values = values + [next_value]
    gae = 0.0
    advantages = [0.0] * T

    #walk backwards to accumulate
    for t in reversed(range(T)):
        delta = rewards[t] + gamma * values[t+1] - values[t]
        gae = delta + gamma * lam * gae
        advantages[t] = gae

    return torch.tensor(advantages, dtype=torch.float32)


def collect_ppo_data(env, policy, batch_size=256, gamma=0.99, lam=0.95):
    """
    Collect a batch of experience using the current policy for PPO.

    Returns:
      obs_batch : Tensor [batch_size, obs_dim]
      sym_batch : Tensor [batch_size] of symbol indices
      dir_batch : Tensor [batch_size] of direction (0=buy,1=sell)
      qty_batch : Tensor [batch_size] of quantity indices
      logp_batch: Tensor [batch_size] of log probabilities
      adv_batch : Tensor [batch_size] of advantages
      val_batch : Tensor [batch_size] of value estimates V(s_t)
    """
    obs_buf, sym_buf, dir_buf, qty_buf = [], [], [], []
    logp_buf, rew_buf, val_buf = [], [], []

    o = env.reset()
    for _ in range(batch_size):
        # prepare tensor
        o_t = torch.tensor(o, dtype=torch.float32).unsqueeze(0)
        # get policy outputs
        sym_logits, dir_logits, qty_logits, value = policy(o_t)
        # distributions
        sym_dist = Categorical(logits=sym_logits)
        dir_dist = Categorical(logits=dir_logits)
        qty_dist = Categorical(logits=qty_logits)
        # sample
        sym_act = sym_dist.sample()
        dir_act = dir_dist.sample()
        qty_act = qty_dist.sample()
        # combined log prob
        logp = sym_dist.log_prob(sym_act) + dir_dist.log_prob(dir_act) + qty_dist.log_prob(qty_act)
        # map to env action
        action = {
            "type":   "buy" if dir_act.item() == 0 else "sell",
            "symbol": env.symbols[sym_act.item()],
            "qty":    env.qty_options[qty_act.item()]
        }
        # step
        next_o, r, done, _ = env.step(action)
        # record
        obs_buf.append(o)
        sym_buf.append(sym_act.item())
        dir_buf.append(dir_act.item())
        qty_buf.append(qty_act.item())
        logp_buf.append(logp.item())
        rew_buf.append(r)
        val_buf.append(value.item())
        # advance state
        o = next_o
        if done:
            o = env.reset()
    # bootstrap value for last state
    o_t = torch.tensor(o, dtype=torch.float32).unsqueeze(0)
    _, _, _, next_val_tensor = policy(o_t)
    next_val = next_val_tensor.item()
    # compute advantages
    adv_buf = compute_gae(rew_buf, val_buf, next_val, gamma, lam)
    # turn into tensors
    obs_batch = torch.tensor(obs_buf, dtype=torch.float32)
    sym_batch = torch.tensor(sym_buf, dtype=torch.int64)
    dir_batch = torch.tensor(dir_buf, dtype=torch.int64)
    qty_batch = torch.tensor(qty_buf, dtype=torch.int64)
    logp_batch= torch.tensor(logp_buf, dtype=torch.float32)
    val_batch = torch.tensor(val_buf, dtype=torch.float32)
    return obs_batch, sym_batch, dir_batch, qty_batch, logp_batch, adv_buf, val_batch


def local_adapt(global_state_dict, env: TradingEnv):
    """
    Perform one round of local adaptation (inner loop) using PPO + first-order MAML.
    Returns the parameter difference Δθ = θ' - θ.
    """
    #initialize policy with global weights
    policy = PolicyNet(obs_dim=3, n_symbols=71, n_qtys=4) #need to suply obs_dim, n_symbols, n_qtys here from local_adapt, but how?
    policy.load_state_dict(global_state_dict)

    #sample a batch D_theta under θ
    #need to implement some trajectory collection / PPO data collector here)

    obs_batch, act_batch, old_logp_batch, adv_batch = collect_ppo_data(env, policy)

    # INNER_STEPS of PPO-style updates on that batch
    optimizer = SGD(policy.parameters(), lr=LOCAL_LR)
    for _ in range(INNER_STEPS):
        loss = ppo_clipped_loss(policy, obs_batch, act_batch, old_logp_batch, adv_batch)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    #computes Δθ = θ' - θ
    new_state = policy.state_dict()
    delta = {k: new_state[k] - global_state_dict[k] for k in global_state_dict}
    return delta


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Federated RL client")
    parser.add_argument('--host', default='127.0.0.1', help='Trading server host')
    parser.add_argument('--port', default=50004, type=int, help='Trading server port')
    parser.add_argument('--user', required=True, help='Username for this client')
    args = parser.parse_args()

   
    global_weights = get_global_weights()
    env = TradingEnv(args.host, args.port, args.user)
    delta = local_adapt(global_weights, env)

    #submit delta back to server
    result = submit_delta(delta)
    print("Submission result:", result)


if __name__ == '__main__':
    main()
