"""
Paper-trading engine: place / cancel orders and update balances.
Market orders fill immediately at the given reference price.
Limit orders stay open until cancelled (or you can add a matcher later).
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
import uuid

from . import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "ord") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def place_order(
    symbol: str,
    side: str,
    order_type: str,
    amount: float,
    price: Optional[float] = None,
    market_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Place a paper order.

    - market  → fills immediately at market_price (required)
    - limit   → rests as 'open'; balances are locked
    """
    side = side.lower()
    order_type = order_type.lower()
    symbol = symbol.upper().replace("-", "/")

    if amount <= 0:
        return {"success": False, "message": "Amount must be > 0"}

    base, quote = symbol.split("/")
    now = _now()
    order_id = _new_id("ord")

    if order_type == "market":
        if not market_price or market_price <= 0:
            return {"success": False, "message": "Market order needs a valid market price"}
        fill_price = float(market_price)
        cost = amount * fill_price

        if side == "buy":
            usdt = db.get_balance(quote)
            if usdt < cost:
                return {"success": False, "message": f"Insufficient {quote}: need {cost:.4f}, have {usdt:.4f}"}
            db.adjust_balance(quote, -cost)
            db.adjust_balance(base, +amount)
        else:  # sell
            coin = db.get_balance(base)
            if coin < amount:
                return {"success": False, "message": f"Insufficient {base}: need {amount}, have {coin}"}
            db.adjust_balance(base, -amount)
            db.adjust_balance(quote, +cost)

        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "type": "market",
            "price": fill_price,
            "amount": amount,
            "filled": amount,
            "status": "closed",
            "created_at": now,
            "updated_at": now,
        }
        db.insert_order(order)
        trade = {
            "id": _new_id("trd"),
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "price": fill_price,
            "amount": amount,
            "created_at": now,
        }
        db.insert_trade(trade)
        return {"success": True, "message": f"✓ Market {side} filled @ {fill_price}", "order": order}

    # ---- limit ----
    if not price or price <= 0:
        return {"success": False, "message": "Limit order requires a valid price"}

    price = float(price)
    cost = amount * price

    if side == "buy":
        usdt = db.get_balance(quote)
        if usdt < cost:
            return {"success": False, "message": f"Insufficient {quote}: need {cost:.4f}, have {usdt:.4f}"}
        # lock funds
        db.adjust_balance(quote, -cost, +cost)
    else:
        coin = db.get_balance(base)
        if coin < amount:
            return {"success": False, "message": f"Insufficient {base}: need {amount}, have {coin}"}
        db.adjust_balance(base, -amount, +amount)

    order = {
        "id": order_id,
        "symbol": symbol,
        "side": side,
        "type": "limit",
        "price": price,
        "amount": amount,
        "filled": 0.0,
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    db.insert_order(order)
    return {"success": True, "message": f"✓ Limit {side} resting @ {price}", "order": order}


def cancel_order(order_id: str) -> Dict[str, Any]:
    order = db.get_order(order_id)
    if not order:
        return {"success": False, "message": "Order not found"}
    if order["status"] != "open":
        return {"success": False, "message": f"Order is {order['status']}, cannot cancel"}

    base, quote = order["symbol"].split("/")
    remaining = order["amount"] - order["filled"]
    price = order["price"] or 0

    # unlock
    if order["side"] == "buy":
        cost = remaining * price
        db.adjust_balance(quote, +cost, -cost)
    else:
        db.adjust_balance(base, +remaining, -remaining)

    now = _now()
    db.update_order(order_id, status="canceled", updated_at=now)
    return {"success": True, "message": f"Cancelled {order_id}"}


def fill_limit_order(order_id: str, fill_price: Optional[float] = None) -> Dict[str, Any]:
    """Manually fill an open limit order (useful for demos / simple matching)."""
    order = db.get_order(order_id)
    if not order or order["status"] != "open":
        return {"success": False, "message": "No open order with that id"}

    base, quote = order["symbol"].split("/")
    remaining = order["amount"] - order["filled"]
    price = fill_price or order["price"]
    cost = remaining * price
    now = _now()

    # release lock and credit the other side
    if order["side"] == "buy":
        locked_cost = remaining * (order["price"] or price)
        db.adjust_balance(quote, 0, -locked_cost)   # unlock
        # if fill cheaper, refund difference
        if price < (order["price"] or price):
            db.adjust_balance(quote, locked_cost - cost)
        db.adjust_balance(base, +remaining)
    else:
        db.adjust_balance(base, 0, -remaining)
        db.adjust_balance(quote, +cost)

    db.update_order(
        order_id,
        filled=order["amount"],
        status="closed",
        price=price,
        updated_at=now,
    )
    trade = {
        "id": _new_id("trd"),
        "order_id": order_id,
        "symbol": order["symbol"],
        "side": order["side"],
        "price": price,
        "amount": remaining,
        "created_at": now,
    }
    db.insert_trade(trade)
    return {"success": True, "message": f"Filled {order_id} @ {price}", "trade": trade}
