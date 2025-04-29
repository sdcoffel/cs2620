# Stock Trading Simulator with Federated Learning

A real-time stock trading platform with dynamic price updates using Geometric Brownian Motion and reinforcement learning capabilities.

## System Overview

This project implements a client-server stock trading platform that allows users to:
- Register and maintain persistent portfolios
- Buy and sell stocks at dynamically changing prices
- Track portfolio performance (unrealized and realized profits)
- Participate in federated learning to improve trading strategies
- Visualize trading performance through analytics graphs

## Architecture

The system follows a client-server architecture with the following components:

### Server Components
- **server.py**: Main server that handles client connections, trading operations, and federated learning aggregation
- **stockpricemanager.py**: Price simulation engine using Geometric Brownian Motion (GBM)

### Client Component
- **client.py**: Terminal-based client interface with automated trading capabilities using reinforcement learning

### Data Files
- **stocks.txt**: Current stock prices that are updated in real-time
- **currency.txt**: Exchange rates between currencies
- **clients.txt**: Persistent storage of user portfolios

### Testing Components
- **unittests.py**: Comprehensive unit tests for both server and client components
- **integrationtests.py**: Integration tests for the complete system
- **GBMvisualization.py**: Visualization tool for Geometric Brownian Motion

## Key Design Choices

### 1. Stock Price Simulation with Geometric Brownian Motion

The system uses Geometric Brownian Motion (GBM) to simulate realistic stock price movements. This approach is widely used in financial modeling to generate price paths that exhibit properties of real-world stock prices.

GBM Formula:
```
S(t+Δt) = S(t) * exp((μ - 0.5σ²)Δt + σ√Δt * Z)
```
Where:
- S(t): Current stock price
- μ: Drift coefficient (expected return)
- σ: Volatility (standard deviation of returns)
- Δt: Time step (fraction of a year)
- Z: Random sample from a standard normal distribution

The default parameters are:
- Update interval: 5 seconds
- Expected daily drift (μ): 1.0
- Daily volatility (σ): 1.0
- Time step (Δt): 1/252 (representing trading days per year)

### 2. Concurrent Thread-based Design

The server implements a thread-based concurrency model to handle multiple clients simultaneously:
- Each client connection runs in its own dedicated thread
- The stock price manager runs in a separate thread to update prices at regular intervals
- Thread locks (`state_lock`) ensure data consistency during concurrent operations
- The scheduler manages timed events for regular price updates

### 3. Atomic File Operations

To ensure data integrity, the system implements atomic file operations:
- Uses temporary files and OS-level atomic replace operations
- Prevents data corruption during crashes or interruptions
- Stores data in human-readable JSON format

### 4. Portfolio Management

The system implements comprehensive portfolio tracking:
- Tracks shares, cost basis, percentage change, and profit/loss for each stock
- Calculates both unrealized and realized profits
- Updates portfolio values in real-time as stock prices change
- Enforces share limits (maximum 200 shares per stock)

### 5. Federated Learning for Automated Trading

The system implements a reinforcement learning approach with federated learning capabilities:
- Clients maintain local models that learn from trading actions
- The server aggregates model updates from all clients
- Clients periodically pull the global model to improve local decision-making
- The model predicts potential profits based on price changes and historical performance

Key federated learning components:
- Local model training with gradient descent
- Weight aggregation on the server
- Accuracy and loss tracking for model evaluation
- Performance visualization through matplotlib

### 6. Message-based Communication Protocol

The client-server communication uses a JSON-based message protocol:
- Newline-separated JSON messages
- Consistent response format with status codes
- Buffer management for partial messages
- Command-based API for all operations

## Technical Details

### Server Configuration
- Default host: localhost
- Default port: 50004
- Buffer size: 2048 bytes

### Portfolio Data Structure
Each user's portfolio is stored as:
```json
{
  "SYMBOL": [shares, price, percent_change, profit]
}
```

### Federated Learning Model
The model uses a simple linear architecture:
- Input features: price change, action taken
- Weights: [w0, w1, w2]
- Prediction: w0 + w1*Δp + w2*action
- Training: Mean squared error loss with gradient descent

## Getting Started

### Starting the Server
```bash
python server.py
```

### Starting the Stock Price Manager (if running separately)
```bash
python stockpricemanager.py
```

### Connecting a Client
```bash
python client.py
```

### Client Commands
- Enter your username when prompted to register/login
- The client will automatically start trading based on its reinforcement learning model
- Press Ctrl+C to interrupt trading and view analytics graphs

## Implementation Notes

### Thread Safety
- All state modifications are protected by the `state_lock`
- Atomic file operations ensure data consistency even during crashes

### Trading Limits
- Maximum 200 shares per stock enforced on purchases
- Cannot sell more shares than owned

### Visualization
After ending a trading session (Ctrl+C), the client displays:
1. Net profit over time
2. Loss history of the training model
3. Prediction accuracy of the model

## Testing

The project includes comprehensive test suites:

### Unit Tests (`unittests.py`)
- Tests for all server components
- Tests for client functionality
- Tests for the stock price manager
- Command: `pytest --cov=. --cov-report=term-missing unittests.py`

### Integration Tests (`integrationtests.py`)
- Tests for normal trading flows
- Tests for federated learning flows
- Tests for stock price updates
- Command: `pytest integrationtests.py`

## Key Developer Information

### Code Organization
- The project follows a procedural style with global state management
- Thread safety is maintained through explicit locking
- Federated learning components are tightly integrated with trading functionality

### Adding New Features
1. For new trading commands:
   - Add the command handler in `server.py` within the `process_request` method
   - Implement corresponding client functionality in `client.py`
   
2. For modifying the price simulation:
   - Adjust the GBM parameters in `stockpricemanager.py`
   
3. For extending federated learning:
   - Modify the `train_local_model` method in the client
   - Update the aggregation logic in the server's `update_model` command handler

### Known Limitations
- No user authentication beyond username
- Limited error handling for network disruptions
- Simplistic reinforcement learning model
- No database backend for truly persistent storage

### Future Enhancements
- Enhanced security with proper authentication
- More sophisticated reinforcement learning models
- Additional order types (limit orders, stop-loss)
- Implementation of real-world market constraints
- Expanded visualization capabilities
- Support for additional asset classes beyond stocks