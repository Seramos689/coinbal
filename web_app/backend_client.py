"""
HTTP client that talks to the paper-trading backend.
Used by the Dash UI instead of (or alongside) Binance.
"""

from typing import Dict, Any, Optional, List
import os
import requests

# Reads the backend URL from environment variable (set this on Render)
# Falls back to localhost when running on your computer
DEFAULT_BASE = os.getenv("PAPER_API_URL", "http://127.0.0.1:8000")


class PaperBackendClient:
    def __init__(self, base_url: str = DEFAULT_BASE):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def health(self) -> bool:
        try:
            r = self.session.get(self._url("/api/health"), timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def get_balances(self) -> Dict[str, float]:
        r = self.session.get(self._url("/api/balances"), timeout=5)
        r.raise_for_status()
        return r.json()

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        market_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "price": price,
            "market_price": market_price,
        }
        r = self.session.post(self._url("/api/orders"), json=payload, timeout=10)
        if r.status_code >= 400:
            detail = r.json().get("detail", r.text)
            return {"success": False, "message": str(detail)}
        return r.json()

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        params = {"status": "open"}
        if symbol:
            params["symbol"] = symbol
        r = self.session.get(self._url("/api/orders"), params=params, timeout=5)
        r.raise_for_status()
        return r.json()

    def fetch_order_history(self, symbol: Optional[str] = None) -> List[Dict]:
        params = {"status": "closed,canceled"}
        if symbol:
            params["symbol"] = symbol
        r = self.session.get(self._url("/api/orders"), params=params, timeout=5)
        r.raise_for_status()
        return r.json()

    def fetch_trades(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        params: Dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        r = self.session.get(self._url("/api/trades"), params=params, timeout=5)
        r.raise_for_status()
        return r.json()

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        r = self.session.delete(self._url(f"/api/orders/{order_id}"), timeout=5)
        if r.status_code >= 400:
            detail = r.json().get("detail", r.text)
            return {"success": False, "message": str(detail)}
        return r.json()

    def reset(self) -> Dict[str, Any]:
        r = self.session.post(self._url("/api/reset"), timeout=5)
        r.raise_for_status()
        return r.json()


# Singleton – automatically uses PAPER_API_URL if set
paper = PaperBackendClient()
