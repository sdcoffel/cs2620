# Stock Trading System

A real-time stock trading simulator with dynamic price updates using Geometric Brownian Motion to model market behavior.

## System Overview

This project implements a client-server stock trading platform that allows users to:
- Register and maintain persistent portfolios
- Buy and sell stocks at dynamically changing prices
- Track portfolio performance including realized and unrealized profits

## Architecture

The system follows a client-server architecture with the following components:

### Server Components
- **server.py**: Main server that handles client connections and requests
- **data_management.py**: Core logic for processing client requests and portfolio management
- **stockpricemanager.py**: Price simulation engine using Geometric Brownian Motion

### Client Component
- **client.py**: Terminal-based client interface for connecting to the server and executing trades

### Data Files
- **stocks.txt**: Current stock prices that are updated in real-time
- **currency.txt**: Exchange rates between currencies
- **clients.txt**: Persistent storage of user portfolios

## Key Design Choices

### 1. Real-time Price Simulation
- Uses Geometric Brownian Motion to simulate realistic stock price movements
- Implements the formula: S(t+Δt) = S(t)exp((μ− 1/2σ²)Δt + σ√Δt Z)
- Parameters include drift (μ), volatility (σ), and time step (Δt)
- Updates stock prices at regular intervals (every 5 seconds by default)

### 2. Thread-based Concurrency Model
- Each client runs in its own thread to handle simultaneous connections
- Background thread for continuous price updates
- Thread locks (state_lock) to ensure data consistency during concurrent access

### 3. Atomic File Operations
- Implements safe file operations using temporary files and OS-level atomic replace
- Prevents data corruption during file updates
- Uses JSON for simple and human-readable data storage

### 4. Portfolio Calculations
- Real-time calculation of unrealized and realized profits
- Accurate tracking of cost basis during multiple buy/sell operations
- Percentage change tracking for each position

### 5. Message-based Protocol
- Newline-separated JSON messages for client-server communication
- Consistent response format with status codes and error messages
- Buffer management to handle partial messages

## Technical Details

### Server Configuration
- Default host: 10.253.137.44
- Default port: 50004
- Buffer size: 1024 bytes

### Stock Price Parameters
- Update interval: 5 seconds
- Expected daily drift (μ): 0.0005
- Daily volatility (σ): 0.02
- Time step (Δt): 1/252 (representing trading days per year)

### Portfolio Data Structure
Each user's portfolio is stored as:
```
{
  "SYMBOL": [shares, price, percent_change, profit],
  ...
}
```

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
python client.py [--host HOST] [--port PORT]
```

### Client Commands
- `portfolio`: Display current holdings
- `buy SYMBOL QTY`: Purchase shares
- `sell SYMBOL QTY`: Sell shares
- `quit`: Exit the application

## Implementation Notes

### Profit Calculation
- The system tracks both realized and unrealized profits
- Cost basis is recalculated using weighted average after each buy
- When selling, profit is realized based on the difference between current price and cost basis

### Thread Safety
- All state modifications are protected by the state_lock
- Atomic file operations ensure data consistency even during crashes

### Future Enhancements
- Currency conversion for international trading
- Additional order types (limit orders, stop loss)
- Performance optimization for high-frequency trading
- Authentication and security improvements

## Developer Guidelines

### Adding New Features
1. Server-side changes typically require modifications to `data_management.py`
2. New client commands should be added to both client and server components
3. Update the state storage schema as needed in all three data files

### Code Style
- The code follows a procedural style with global state management
- State is synchronized between memory and disk regularly
- Thread safety is maintained through explicit locking

### Testing
- Test client registration and portfolio initialization
- Verify buy/sell operations with different quantities
- Ensure price updates propagate correctly to client portfolios
- Check profit calculations match expected values

## Known Limitations
- No user authentication beyond username
- Limited error handling for network disruptions
- Single-server architecture lacks scalability for high load
- No database backend for truly persistent storage