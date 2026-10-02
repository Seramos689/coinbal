# Paper Trading + Binance UI

## What you have now

| Piece | Role |
|-------|------|
| **backend/** | FastAPI paper-trading engine (SQLite) |
| **binance_app.py** | Binance-style UI (chart, order book, form) |
| **trading.py** | Switches between PAPER and Binance |
| **backend_client.py** | HTTP client for the paper API |

Default mode is **PAPER**: balances, buy/sell, open orders and trade history all come from your local backend — not Binance.

---

## Quick start (paper trading)

### Terminal 1 – start the backend

```cmd
cd web_app
pip install -r requirements_web.txt
uvicorn backend.main:app --reload --port 8000
```

You should see: `Uvicorn running on http://127.0.0.1:8000`

### Terminal 2 – start the UI

```cmd
cd web_app
python binance_app.py
```

Open: **http://127.0.0.1:8050**

Header badge should show **PAPER**.

### Place a paper trade

1. Pick a pair (e.g. BTC/USDT)
2. Buy or Sell tab
3. Limit or Market
4. Enter amount (and price for Limit)
5. Click the button

- Market orders fill instantly and update balances  
- Limit orders appear under **Open Orders**  
- Balances in the header update after each fill  

Starting paper balances: **10 000 USDT**, 0.15 BTC, 2 ETH, etc.

Reset anytime:

```bash
curl -X POST http://127.0.0.1:8000/api/reset
```

---

## .env settings

```env
# paper (default) | binance
TRADING_MODE=paper

# only used when TRADING_MODE=binance
BINANCE_TESTNET=true
BINANCE_API_KEY=
BINANCE_API_SECRET=
```

---

## Backend API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Health check |
| GET | /api/balances | All free balances |
| POST | /api/orders | Place order |
| GET | /api/orders?status=open | Open orders |
| GET | /api/orders?status=closed,canceled | History |
| DELETE | /api/orders/{id} | Cancel |
| GET | /api/trades | Executed trades |
| POST | /api/reset | Reset paper account |

Example place order:

```bash
curl -X POST http://127.0.0.1:8000/api/orders ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"BTC/USDT\",\"side\":\"buy\",\"type\":\"market\",\"amount\":0.001,\"market_price\":65000}"
```

---

## Switch to real Binance later

1. Set `TRADING_MODE=binance` in `.env`
2. Add real API keys
3. Restart `python binance_app.py`

Chart / order book / market trades still use public Binance data either way.
