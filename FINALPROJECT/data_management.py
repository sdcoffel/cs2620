#helpers go here

import threading 
from sched import scheduler
import os 
import json 

#goal: maximize the 'net profit' field

#state_lock = threading.Lock()

#json functions 
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

