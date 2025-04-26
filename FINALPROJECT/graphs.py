import matplotlib.pyplot as plt
import numpy as np
from client import TradingClient

client = TradingClient()
data = client.analytics

time = np.arange(len(data))  # Create a time array based on the length of the data - 1 instance per data point
print(data)
# plt.figure(figsize=(10, 6))
# plt.plot(time, data, marker='o', linestyle='-', color='b', label='Net Profit')
# plt.title('Net Profit Over Time')
# plt.xlabel('Time')
# plt.ylabel('Net Profit ($)')
# plt.legend()
# plt.grid(True)
# plt.show()

