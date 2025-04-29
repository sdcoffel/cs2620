#for all intents and purposes, this is the stock market
#model price changes via geometric brownian motion 
# after discretizing the stochastic diffeq, we get a solution of the form: S t+Δt = St​exp((μ− 1/2​ σ**2 )Δt+σ Δt**1/2 Z)

#update: i was right. the RL becomes very easy to predict if i give it favorable hyperparamters
#BIIIG ASSUMPTION HERE: if i use the current hyperparameters in GBM, i am assuming that the market tends to get better over time. this is a big assumption. 

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
MU              = 1   # expected daily drift
SIGMA           = 1     # daily volatility
DT              = 1/252    # fraction of year per “day”


#atomic writes / saves 
def load_json(path):
    """
    Loads a JSON object from a file if it exists, otherwise returns a default value.

    Args: path (str): The file path to the JSON file.
        default (Any): The default value to return if the file does not exist.

    Returns: Any: The loaded JSON object if the file exists, otherwise the default value.
    """
        
    with open(path, "r") as f:
        return json.load(f)  # throws FileNotFoundError or JSONDecodeError


def save_json(path, data):
    """
    This function writes the JSON data to a temporary file first and then
    replaces the original file with the temporary file. This ensures that
    the file is not corrupted if the program crashes during the write process.

    Args: path (str): The file path where the JSON data should be saved.
        data (dict): The dictionary data to be serialized and saved as JSON.

    Returns: None
    Raises: OSError: If there is an issue writing to the file or replacing it.
        TypeError: If the data provided is not serializable to JSON.
    """

    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path) #atomic writing to the stocks database to prevent race conditions


#GBM price simulation 
def simulate_prices(sc):
    """
    Simulates and updates stock prices using the Geometric Brownian Motion (GBM) model.
    This function loads the current stock prices from a JSON file, applies the GBM formula
    to simulate new prices, and saves the updated prices back to the JSON file. It also
    schedules the next update using the provided scheduler.

    Args: sc (sched.scheduler): The scheduler instance used to schedule the next update.
    Returns: None

    GBM Formula:
        S_new = S * exp((μ - 0.5σ²)Δt + σ√Δt * Z)
        where:
            - S: Current stock price
            - μ: Drift coefficient (expected return)
            - σ: Volatility (standard deviation of returns)
            - Δt: Time step
            - Z: Random sample from a standard normal distribution
    """

    prices = load_json(STOCK_FILE)
    new_prices = {}
    for sym, S in prices.items():
        #sample Z ~ N(0,1)
        Z = random.gauss(0,1)
        #GBM update: S * exp((μ - 0.5σ²)Δt + σ√Δt Z)
        S_new = S * math.exp((MU - 0.5*SIGMA**2)*DT + SIGMA*math.sqrt(DT)*Z)
        new_prices[sym] = round(S_new, 2)
    save_json(STOCK_FILE, new_prices)
    print(f"[{time.ctime()}] Updated prices: {new_prices}")
    # re‑schedule the next update
    sc.enter(UPDATE_INTERVAL, 1, simulate_prices, (sc,))


#let this run in the background while the server is running - maybe incorporate this into the server later after i test
def main():
    """
    Main function to fire up the stock price manager (simulates the stock market)."""

    print("Stock Price Manager firing up...")
    scheduler = sched.scheduler(time.time, time.sleep)
    # schedule first immediate call (delay=0)
    scheduler.enter(0, 1, simulate_prices, (scheduler,))
    scheduler.run()  # blocks, running scheduled simulations in real time



if __name__ == "__main__":
    """Main driver."""

    main()


