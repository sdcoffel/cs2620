#model price changes via geometric brownian motion - although we could change this: 
# after discretizing the stochastic diffeq, we have: S t+Δt = St​exp((μ− 1/2​ σ**2 )Δt+σ Δt**1/2 Z)

import sched 
import time 
import json 
import random 
import math
import os 
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent
STOCK_FILE = "stocks.txt"

UPDATE_INTERVAL = 5        # seconds between updates
MU              = 0.0005   # expected daily drift
SIGMA           = 0.02     # daily volatility
DT              = 1/252    # fraction of year per “day”

#atomic writes / saves 
def load_json(path):
    with open(path, "r") as f:
        return json.load(f)  # throws FileNotFoundError or JSONDecodeError


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path) #atomic writing to the stocks database to prevent race conditions


#GBM price simulation 
def simulate_prices(sc):
    prices = load_json(STOCK_FILE)
    new_prices = {}
    for sym, S in prices.items():
        # sample Z ~ N(0,1)
        Z = random.gauss(0,1)
        # GBM update: S * exp((μ - 0.5σ²)Δt + σ√Δt Z)
        S_new = S * math.exp((MU - 0.5*SIGMA**2)*DT + SIGMA*math.sqrt(DT)*Z)
        new_prices[sym] = round(S_new, 2)
    save_json(STOCK_FILE, new_prices)
    print(f"[{time.ctime()}] Updated prices: {new_prices}")
    # re‑schedule the next update
    sc.enter(UPDATE_INTERVAL, 1, simulate_prices, (sc,))

#let this run in the background while the server is running - maybe incorporate this into the server later after i test
def main():
    print("Stock Price Manager starting...")
    scheduler = sched.scheduler(time.time, time.sleep)
    # schedule first immediate call (delay=0)
    scheduler.enter(0, 1, simulate_prices, (scheduler,))
    scheduler.run()  # blocks, running scheduled simulations in real time

if __name__ == "__main__":
    main()


