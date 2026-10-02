"""
Trading layer – PAPER mode uses local engine (no HTTP required).
When PAPER_API_URL is set (Render two-service setup), it uses the remote FastAPI backend.

.env:
  TRADING_MODE=paper     (default)
  TRADING_MODE=binance
  PAPER_API_URL=https://your-backend.onrender.com   (optional, for remote paper)
"""

import os
import sys
from pathlib import Path
from time import time
from typing import Optional, Dict, Any, List

try:
    import ccxt
except ImportError:
    ccxt = None
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / ".env")

TRADING_MODE = os.getenv("TRADING_MODE", "paper").strip().lower()


class BinanceTrader:
    def __init__(self):
        self.mode = TRADING_MODE
        self.api_key = os.getenv("BINANCE_API_KEY", "").strip()
        self.api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
        self.testnet = os.getenv("BINANCE_TESTNET", "true").lower() in ("1", "true", "yes")
        self.exchange = None
        self.simulation = False
        self._use_local_paper = False
        self._use_http_paper = False
        self._http_client = None

        if self.mode == "paper":
            self._init_paper()
        else:
            self._init_binance()

    def _init_paper(self):
        """Use remote FastAPI backend if PAPER_API_URL is set, otherwise local SQLite."""
        paper_api = os.getenv("PAPER_API_URL", "").strip()

        if paper_api:
            # Remote backend mode (two-service setup on Render)
            try:
                from backend_client import PaperBackendClient
                self._http_client = PaperBackendClient(paper_api)
                if self._http_client.health():
                    self._use_local_paper = False
                    self._use_http_paper = True
                    print(f"[Trader] PAPER mode – remote API: {paper_api}")
                    return
                else:
                    print(f"[Trader] Remote API not reachable: {paper_api} – falling back to local")
            except Exception as e:
                print(f"[Trader] Failed to init remote paper client: {e} – falling back to local")

        # Fallback: local in-process SQLite engine
        try:
            from backend import db, engine as paper_engine
            db.init_db()
            self._paper_engine = paper_engine
            self._paper_db = db
            self._use_local_paper = True
            self._use_http_paper = False
            print("[Trader] PAPER mode – local engine (SQLite) ready")
            print(f"         Balances: {db.get_balances()}")
        except Exception as e:
            print(f"[Trader] PAPER local engine failed: {e}")
            self.simulation = True
            self._use_local_paper = False
            self._use_http_paper = False

    def _init_binance(self):
        if not (self.api_key and self.api_secret):
            print("[Trader] No API keys – use TRADING_MODE=paper for paper trading")
            self.simulation = True
            self.exchange = ccxt.binance({"enableRateLimit": True}) if ccxt else None
            return
        config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
                "adjustForTimeDifference": True,
                "recvWindow": 10000,
            },
        }
        if ccxt is None:
            print("[Trader] ccxt not installed")
            self.simulation = True
            return
        self.exchange = ccxt.binance(config)
        if self.testnet:
            self.exchange.set_sandbox_mode(True)
            print("[Trader] Binance TESTNET")
        else:
            print("[Trader] Binance LIVE – real money")
        try:
            self.exchange.load_time_difference()
            self.exchange.fetch_balance()
            print("[Trader] Keys OK")
        except Exception as e:
            print(f"[Trader] Key check failed: {e} → simulation")
            self.simulation = True

    def mode_label(self) -> str:
        if self._use_http_paper:
            return "PAPER (remote)"
        if self.mode == "paper" and self._use_local_paper:
            return "PAPER"
        if self.simulation:
            return "SIMULATION"
        if self.mode == "paper":
            return "PAPER"
        return "TESTNET" if self.testnet else "LIVE"

    def get_balances(self) -> Dict[str, float]:
        if self._use_http_paper and self._http_client:
            try:
                return self._http_client.get_balances()
            except Exception as e:
                print(f"[Trader] remote balances error: {e}")
                return {}
        if self._use_local_paper:
            try:
                return self._paper_db.get_balances()
            except Exception as e:
                print(f"[Trader] balances error: {e}")
                return {}
        if self.simulation or not self.exchange:
            return {"USDT": 10000.0, "BTC": 0.15, "ETH": 2.0}
        try:
            bal = self.exchange.fetch_balance()
            free = bal.get("free", {})
            return {k: float(v) for k, v in free.items() if float(v or 0) > 0}
        except Exception:
            return {}

    def get_balance(self, asset: str = "USDT") -> float:
        return float(self.get_balances().get(asset, 0) or 0)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        market_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        side = side.lower()
        order_type = order_type.lower()
        if amount <= 0:
            return {"success": False, "message": "Amount must be > 0"}
        if order_type == "limit" and (not price or price <= 0):
            return {"success": False, "message": "Limit needs a price"}

        # Remote paper backend
        if self._use_http_paper and self._http_client:
            try:
                return self._http_client.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    amount=amount,
                    price=price,
                    market_price=market_price or price,
                )
            except Exception as e:
                return {"success": False, "message": f"Remote paper error: {e}"}

        # Local paper engine
        if self._use_local_paper:
            try:
                return self._paper_engine.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    amount=amount,
                    price=price,
                    market_price=market_price or price,
                )
            except Exception as e:
                return {"success": False, "message": f"Paper error: {e}"}

        if self.simulation:
            msg = f"[SIM] {side.upper()} {amount} {symbol}"
            return {"success": True, "message": msg, "order": {"id": f"sim-{int(time())}"}}

        try:
            params = {"recvWindow": 10000}
            if order_type == "market":
                order = self.exchange.create_order(
                    symbol=symbol, type="market", side=side, amount=amount, params=params
                )
            else:
                order = self.exchange.create_order(
                    symbol=symbol, type="limit", side=side,
                    amount=amount, price=price, params=params
                )
            return {
                "success": True,
                "message": f"Order {order.get('id')} ({order.get('status')})",
                "order": order,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        if self._use_http_paper and self._http_client:
            try:
                return self._http_client.fetch_open_orders(symbol=symbol)
            except Exception:
                return []
        if self._use_local_paper:
            try:
                return self._paper_db.get_orders(status="open", symbol=symbol)
            except Exception:
                return []
        if self.simulation or not self.exchange:
            return []
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception:
            return []

    def fetch_order_history(self, symbol: Optional[str] = None) -> List[Dict]:
        if self._use_http_paper and self._http_client:
            try:
                return self._http_client.fetch_order_history(symbol=symbol)
            except Exception:
                return []
        if self._use_local_paper:
            try:
                return self._paper_db.get_orders(status="closed,canceled", symbol=symbol)
            except Exception:
                return []
        return []

    def fetch_trades(self, symbol: Optional[str] = None) -> List[Dict]:
        if self._use_http_paper and self._http_client:
            try:
                return self._http_client.fetch_trades(symbol=symbol)
            except Exception:
                return []
        if self._use_local_paper:
            try:
                return self._paper_db.get_trades(symbol=symbol)
            except Exception:
                return []
        return []

    def cancel_order(self, order_id: str, symbol: str = "") -> Dict[str, Any]:
        if self._use_http_paper and self._http_client:
            try:
                return self._http_client.cancel_order(order_id)
            except Exception as e:
                return {"success": False, "message": str(e)}
        if self._use_local_paper:
            try:
                return self._paper_engine.cancel_order(order_id)
            except Exception as e:
                return {"success": False, "message": str(e)}
        if self.simulation:
            return {"success": True, "message": f"[SIM] Cancelled {order_id}"}
        try:
            self.exchange.cancel_order(order_id, symbol)
            return {"success": True, "message": f"Cancelled {order_id}"}
        except Exception as e:
            return {"success": False, "message": str(e)}


trader = BinanceTrader()
