"""
Paper-trading backend API.

Run:
  cd web_app
  uvicorn backend.main:app --reload --port 8000

Endpoints:
  GET  /api/balances
  POST /api/orders
  GET  /api/orders?status=open
  DELETE /api/orders/{id}
  GET  /api/trades
  POST /api/reset
  GET  /api/health
"""

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db, engine

db.init_db()

app = FastAPI(title="Paper Trading API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrderRequest(BaseModel):
    symbol: str = Field(..., example="BTC/USDT")
    side: str = Field(..., example="buy")
    type: str = Field("limit", example="limit")
    amount: float = Field(..., gt=0, example=0.001)
    price: Optional[float] = Field(None, example=65000.0)
    market_price: Optional[float] = Field(
        None, description="Required for market orders (last price from chart)"
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "PAPER"}


@app.get("/api/balances")
def balances():
    return db.get_balances()


@app.post("/api/orders")
def create_order(body: OrderRequest):
    result = engine.place_order(
        symbol=body.symbol,
        side=body.side,
        order_type=body.type,
        amount=body.amount,
        price=body.price,
        market_price=body.market_price,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.get("/api/orders")
def list_orders(
    status: Optional[str] = Query(None, description="open | closed | canceled | comma list"),
    symbol: Optional[str] = None,
):
    return db.get_orders(status=status, symbol=symbol)


@app.delete("/api/orders/{order_id}")
def cancel(order_id: str):
    result = engine.cancel_order(order_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/api/orders/{order_id}/fill")
def fill(order_id: str, market_price: Optional[float] = None):
    """Manually fill a resting limit order (demo helper)."""
    result = engine.fill_limit_order(order_id, fill_price=market_price)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.get("/api/trades")
def trades(symbol: Optional[str] = None, limit: int = 50):
    return db.get_trades(symbol=symbol, limit=limit)


@app.post("/api/reset")
def reset():
    db.reset_paper_account()
    return {"success": True, "message": "Paper account reset", "balances": db.get_balances()}
