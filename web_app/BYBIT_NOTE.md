# Data Source Changed to Bybit

Binance blocks most cloud provider IPs (Render, Railway, Heroku, etc.) with error 451.

This version uses **Bybit** for:
- Candlestick chart data
- Order book
- Recent trades
- Ticker / 24h stats

Paper trading still works exactly the same (local SQLite).

Symbols available: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT, DOGE/USDT
(and most other major pairs supported by Bybit spot).
