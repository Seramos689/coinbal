#!/usr/bin/env python3
"""
Binance-style Trading Interface (Dash)
======================================
Layout mirrors the Binance Spot trading page:

  ┌─────────────────────────────────────────────────────────────┐
  │  Header: Pair · Last Price · 24h Change · High/Low · Volume │
  ├──────────────────────────┬──────────────┬───────────────────┤
  │                          │              │  Recent Trades    │
  │     Candlestick Chart    │  Order Book  │                   │
  │     + Volume             │  (Asks/Bids) ├───────────────────┤
  │                          │              │  Order Form       │
  ├──────────────────────────┤              │  (Buy / Sell)     │
  │  Open Orders / History   │              │                   │
  └──────────────────────────┴──────────────┴───────────────────┘

Run:
  cd web_app
  pip install -r requirements_web.txt
  python binance_app.py

Open: http://127.0.0.1:8050
"""

import sys
import copy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dash
from dash import html, dcc, Input, Output, State, callback, no_update, ALL
import dash_tvlwc
import pandas as pd
import ccxt

from utils.data_feed import BinanceDataFeed
from utils.indicators import add_sma, add_ema, add_bollinger
from trading import trader   # real / testnet / simulation order execution

# ============================================================
# Config
# ============================================================
DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_TF = "1m"
HISTORY_LIMIT = 300
UPDATE_MS = 1500
ORDERBOOK_LIMIT = 12          # rows each side

# Global state (simple process-local cache)
def _get_working_exchange():
    """Try several exchanges until one responds (cloud IPs are often blocked)."""
    candidates = [
        ("okx",     {"enableRateLimit": True}),
        ("kucoin",  {"enableRateLimit": True}),
        ("gate",    {"enableRateLimit": True}),
        ("bybit",   {"enableRateLimit": True, "options": {"defaultType": "spot"}}),
        ("binance", {"enableRateLimit": True}),
    ]
    for name, cfg in candidates:
        try:
            ex = getattr(ccxt, name)(cfg)
            # quick test
            ex.fetch_ticker("BTC/USDT")
            print(f"[Exchange] Using {name.upper()}")
            return ex
        except Exception as e:
            print(f"[Exchange] {name} failed: {str(e)[:60]}")
    print("[Exchange] WARNING: falling back to okx")
    return ccxt.okx({"enableRateLimit": True})

_exchange = trader.exchange or _get_working_exchange()
_feed = None
_last_ticker = {}


def ts_to_unix(t):
    if isinstance(t, datetime):
        return int(t.timestamp())
    return int(t)


def df_to_candles(df: pd.DataFrame) -> list:
    out = []
    for _, r in df.iterrows():
        out.append({
            "time": ts_to_unix(r["time"]),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        })
    return out


def df_to_volume(df: pd.DataFrame) -> list:
    out = []
    for _, r in df.iterrows():
        color = "rgba(14,203,129,0.5)" if r["close"] >= r["open"] else "rgba(246,70,93,0.5)"
        out.append({
            "time": ts_to_unix(r["time"]),
            "value": float(r["volume"]),
            "color": color,
        })
    return out


def df_to_line(df: pd.DataFrame, col: str) -> list:
    out = []
    for _, r in df.iterrows():
        if pd.isna(r[col]):
            continue
        out.append({"time": ts_to_unix(r["time"]), "value": float(r[col])})
    return out


def load_chart_series(symbol: str, timeframe: str):
    global _feed
    _feed = BinanceDataFeed(symbol=symbol, timeframe=timeframe)
    df = _feed.fetch_historical(limit=HISTORY_LIMIT)
    df = add_sma(df, 7)
    df = add_sma(df, 25)
    df = add_sma(df, 99)

    series = [
        {
            "id": "price",
            "type": "candlestick",
            "data": df_to_candles(df),
            "options": {
                "upColor": "#0ecb81",
                "downColor": "#f6465d",
                "borderUpColor": "#0ecb81",
                "borderDownColor": "#f6465d",
                "wickUpColor": "#0ecb81",
                "wickDownColor": "#f6465d",
            },
        },
        {
            "id": "volume",
            "type": "histogram",
            "data": df_to_volume(df),
            "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""},
            "pane": 1,
        },
        {
            "id": "ma7",
            "type": "line",
            "data": df_to_line(df, "SMA_7"),
            "options": {"color": "#f0b90b", "lineWidth": 1},
        },
        {
            "id": "ma25",
            "type": "line",
            "data": df_to_line(df, "SMA_25"),
            "options": {"color": "#a855f7", "lineWidth": 1},
        },
        {
            "id": "ma99",
            "type": "line",
            "data": df_to_line(df, "SMA_99"),
            "options": {"color": "#06b6d4", "lineWidth": 1},
        },
    ]
    return series, df


def fetch_orderbook(symbol: str, limit: int = ORDERBOOK_LIMIT):
    try:
        ob = _exchange.fetch_order_book(symbol, limit=limit)
        asks = sorted(ob.get("asks") or [], key=lambda x: x[0])[:limit]
        bids = sorted(ob.get("bids") or [], key=lambda x: x[0], reverse=True)[:limit]
        return asks, bids
    except Exception as e:
        print(f"[orderbook] {e}")
        return [], []


def fetch_recent_trades(symbol: str, limit: int = 30):
    try:
        trades = _exchange.fetch_trades(symbol, limit=limit)
        rows = []
        for t in reversed(trades):          # newest first
            rows.append({
                "price": t["price"],
                "amount": t["amount"],
                "side": t.get("side", "buy"),
                "time": datetime.fromtimestamp(t["timestamp"] / 1000).strftime("%H:%M:%S"),
            })
        return rows
    except Exception:
        return []


def fetch_ticker(symbol: str):
    try:
        t = _exchange.fetch_ticker(symbol)
        return {
            "last": t.get("last"),
            "change": t.get("percentage"),
            "high": t.get("high"),
            "low": t.get("low"),
            "baseVolume": t.get("baseVolume"),
            "quoteVolume": t.get("quoteVolume"),
        }
    except Exception as e:
        print(f"[ticker] {e}")
        return {}


# ============================================================
# App
# ============================================================
app = dash.Dash(
    __name__,
    title="Trading Interface (Bybit data)",
    update_title=None,
    suppress_callback_exceptions=True,
    external_stylesheets=[],          # we use assets/binance.css
)

print("Loading initial data …")
try:
    INIT_SERIES, _ = load_chart_series(DEFAULT_SYMBOL, DEFAULT_TF)
    candle_count = len(INIT_SERIES[0]["data"]) if INIT_SERIES else 0
    INIT_TICKER = fetch_ticker(DEFAULT_SYMBOL)
    INIT_ASKS, INIT_BIDS = fetch_orderbook(DEFAULT_SYMBOL)
    INIT_TRADES = fetch_recent_trades(DEFAULT_SYMBOL)
    print(f"Ready – {DEFAULT_SYMBOL} | {candle_count} candles loaded")
    if candle_count == 0:
        print("WARNING: 0 candles – chart will be empty. Check exchange access.")
except Exception as e:
    print(f"Init warning: {e}")
    import traceback
    traceback.print_exc()
    INIT_SERIES = [{"id": "price", "type": "candlestick", "data": []}]
    INIT_TICKER = {}
    INIT_ASKS, INIT_BIDS = [], []
    INIT_TRADES = []


def render_header(symbol, ticker):
    last = ticker.get("last") or 0
    change = ticker.get("change") or 0
    high = ticker.get("high") or 0
    low = ticker.get("low") or 0
    vol = ticker.get("baseVolume") or 0
    qvol = ticker.get("quoteVolume") or 0
    up = change >= 0

    mode = trader.mode_label()
    mode_color = "#f0b90b" if mode == "SIMULATION" else ("#0ecb81" if mode == "TESTNET" else "#f6465d")

    # Free balances
    bals = trader.get_balances()
    bal_usdt = bals.get("USDT", 0)
    base = symbol.split("/")[0]
    bal_base = bals.get(base, 0)

    return html.Div([
        html.Div(symbol.replace("/", ""), className="pair"),
        html.Div(f"{last:,.2f}" if last else "—",
                 className=f"price {'up' if up else 'down'}"),
        html.Div([
            html.Span("24h Change", className="label"),
            html.Span(f"{change:+.2f}%" if change else "—",
                      className=f"value {'up' if up else 'down'}"),
        ], className="stat"),
        html.Div([
            html.Span("24h High", className="label"),
            html.Span(f"{high:,.2f}" if high else "—", className="value"),
        ], className="stat"),
        html.Div([
            html.Span("24h Low", className="label"),
            html.Span(f"{low:,.2f}" if low else "—", className="value"),
        ], className="stat"),
        html.Div([
            html.Span("24h Volume", className="label"),
            html.Span(f"{vol:,.2f}" if vol else "—", className="value"),
        ], className="stat"),
        html.Div([
            html.Span("USDT Balance", className="label"),
            html.Span(f"{bal_usdt:,.2f}", className="value"),
        ], className="stat"),
        html.Div([
            html.Span(f"{base} Balance", className="label"),
            html.Span(f"{bal_base:.6f}", className="value"),
        ], className="stat"),
        # Mode badge + selectors
        html.Div([
            html.Span(mode, style={
                "background": mode_color, "color": "#000", "padding": "3px 8px",
                "borderRadius": "4px", "fontWeight": "700", "fontSize": "11px",
                "marginRight": "10px",
            }),
            dcc.Dropdown(
                id="symbol-dd",
                options=[
                    {"label": s, "value": s}
                    for s in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]
                ],
                value=symbol,
                clearable=False,
                style={"width": "130px", "color": "#000", "fontSize": "12px"},
            ),
            dcc.Dropdown(
                id="tf-dd",
                options=[{"label": t, "value": t} for t in ["1m", "5m", "15m", "1h", "4h", "1d"]],
                value=DEFAULT_TF,
                clearable=False,
                style={"width": "80px", "color": "#000", "fontSize": "12px"},
            ),
        ], style={"marginLeft": "auto", "display": "flex", "gap": "8px", "alignItems": "center"}),
    ], className="binance-header", id="header")


def render_orderbook(asks, bids, last_price=None):
    # Some exchanges return [price, qty] others return [price, qty, extra...]
    # Always take only the first two values
    def _pq(entry):
        return float(entry[0]), float(entry[1])

    clean_asks = [_pq(a) for a in asks if len(a) >= 2]
    clean_bids = [_pq(b) for b in bids if len(b) >= 2]

    all_qty = [q for _, q in clean_asks] + [q for _, q in clean_bids]
    max_qty = max(all_qty) if all_qty else 1

    ask_rows = []
    for price, qty in reversed(clean_asks):          # highest ask at top
        pct = min(qty / max_qty * 100, 100)
        ask_rows.append(html.Tr([
            html.Td(f"{price:,.2f}", className="price"),
            html.Td(f"{qty:.5f}"),
            html.Td(f"{price * qty:,.2f}"),
            html.Td(html.Div(className="ob-depth-bar", style={"width": f"{pct}%"})),
        ], className="ob-ask"))

    bid_rows = []
    for price, qty in clean_bids:
        pct = min(qty / max_qty * 100, 100)
        bid_rows.append(html.Tr([
            html.Td(f"{price:,.2f}", className="price"),
            html.Td(f"{qty:.5f}"),
            html.Td(f"{price * qty:,.2f}"),
            html.Td(html.Div(className="ob-depth-bar", style={"width": f"{pct}%"})),
        ], className="ob-bid"))

    mid_price = last_price or (clean_asks[0][0] if clean_asks else 0)

    return html.Div([
        html.Div("Order Book", className="panel-title"),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Price (USDT)"), html.Th("Amount"), html.Th("Total"), html.Th(""),
            ])),
            html.Tbody(ask_rows),
        ], className="ob-table"),
        html.Div(f"{mid_price:,.2f}" if mid_price else "—", className="ob-mid"),
        html.Table([
            html.Tbody(bid_rows),
        ], className="ob-table"),
    ], className="panel orderbook-area", id="orderbook-panel")


def render_trades(trades):
    rows = []
    for t in trades:
        side = t.get("side", "buy")
        rows.append(html.Div([
            html.Span(f"{t['price']:,.2f}", className=f"price {side}"),
            html.Span(f"{t['amount']:.5f}"),
            html.Span(t["time"], className="time"),
        ], className="trade-row"))

    return html.Div([
        html.Div("Market Trades", className="panel-title"),
        html.Div([
            html.Div([
                html.Span("Price", style={"flex": 1}),
                html.Span("Amount", style={"flex": 1, "textAlign": "center"}),
                html.Span("Time", style={"flex": 1, "textAlign": "right"}),
            ], style={"display": "flex", "padding": "4px 10px", "color": "#848e9c", "fontSize": "11px"}),
            html.Div(rows, className="trades-list"),
        ], style={"flex": 1, "overflow": "hidden", "display": "flex", "flexDirection": "column"}),
    ], className="panel trades-area", id="trades-panel")


def render_order_form():
    return html.Div([
        # Buy / Sell always at the top
        html.Div([
            html.Button("Buy", id="tab-buy", className="side-btn active-buy", n_clicks=0),
            html.Button("Sell", id="tab-sell", className="side-btn", n_clicks=0),
        ], className="side-btn-row"),
        html.Div([
            html.Div([
                html.Label("Order Type"),
                dcc.Dropdown(
                    id="order-type",
                    options=[
                        {"label": "Limit", "value": "limit"},
                        {"label": "Market", "value": "market"},
                    ],
                    value="market",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ]),
            html.Div([
                html.Label("Price (USDT)"),
                dcc.Input(id="order-price", type="number", placeholder="0.00", debounce=True),
            ], id="price-row"),
            html.Div([
                html.Label("Amount"),
                dcc.Input(id="order-amount", type="number", placeholder="0.00", debounce=True),
            ]),
            html.Div([
                html.Button("25%", id={"type": "pct", "index": 25}, n_clicks=0),
                html.Button("50%", id={"type": "pct", "index": 50}, n_clicks=0),
                html.Button("75%", id={"type": "pct", "index": 75}, n_clicks=0),
                html.Button("100%", id={"type": "pct", "index": 100}, n_clicks=0),
            ], className="pct-buttons"),
            html.Div([
                html.Label("Total (USDT)"),
                dcc.Input(id="order-total", type="number", placeholder="0.00", disabled=True),
            ]),
            html.Div([
                html.Button("Buy BTC", id="submit-order", className="btn-buy", n_clicks=0),
            ], style={"marginTop": "12px", "paddingBottom": "8px"}),
            html.Div(id="order-msg", style={"color": "#848e9c", "fontSize": "11px", "marginTop": "6px"}),
        ], className="order-body"),
    ], className="panel order-form-area", id="order-form-panel")


# ---------- Layout ----------
app.layout = html.Div([
    # Header
    html.Div(id="header-container", children=render_header(DEFAULT_SYMBOL, INIT_TICKER)),

    # Main trading grid
    html.Div([
        # Chart
        html.Div([
            dash_tvlwc.Tvlwc(
                id="tv-chart",
                series=INIT_SERIES,
                width="100%",
                height=480,
                chartOptions={
                    "layout": {
                        "background": {"type": "solid", "color": "#12161c"},
                        "textColor": "#eaecef",
                    },
                    "grid": {
                        "vertLines": {"color": "rgba(43,49,57,0.5)"},
                        "horzLines": {"color": "rgba(43,49,57,0.5)"},
                    },
                    "crosshair": {"mode": 0},
                    "rightPriceScale": {"borderColor": "#2b3139"},
                    "timeScale": {
                        "borderColor": "#2b3139",
                        "timeVisible": True,
                        "secondsVisible": False,
                    },
                },
            ),
        ], className="panel chart-area"),

        # Order book
        html.Div(id="orderbook-container", children=render_orderbook(INIT_ASKS, INIT_BIDS, INIT_TICKER.get("last"))),

        # Right column: trades + order form
        html.Div([
            html.Div(id="trades-container", children=render_trades(INIT_TRADES)),
            render_order_form(),
        ], className="right-column"),

        # Bottom panel
        html.Div([
            html.Div([
                html.Button("Open Orders", className="bottom-tab active", id="bot-tab-open"),
                html.Button("Order History", className="bottom-tab", id="bot-tab-hist"),
                html.Button("Trade History", className="bottom-tab", id="bot-tab-trade"),
            ], className="bottom-tabs"),
            html.Div(
                f"No open orders ({trader.mode_label()} mode)",
                className="placeholder-msg",
                id="bottom-content",
            ),
        ], className="panel bottom-area"),
    ], className="trading-grid"),

    # Stores & interval
    dcc.Store(id="series-store", data=INIT_SERIES),
    dcc.Store(id="side-store", data="buy"),
    dcc.Interval(id="tick", interval=UPDATE_MS, n_intervals=0),
])


# ============================================================
# Callbacks
# ============================================================

@callback(
    Output("tv-chart", "series"),
    Output("series-store", "data"),
    Output("header-container", "children"),
    Input("symbol-dd", "value"),
    Input("tf-dd", "value"),
)
def on_symbol_or_tf(symbol, tf):
    series, _ = load_chart_series(symbol, tf)
    ticker = fetch_ticker(symbol)
    header = render_header(symbol, ticker)
    return series, series, header


@callback(
    Output("tv-chart", "series", allow_duplicate=True),
    Output("orderbook-container", "children"),
    Output("trades-container", "children"),
    Output("header-container", "children", allow_duplicate=True),
    Output("bottom-content", "children", allow_duplicate=True),
    Input("tick", "n_intervals"),
    State("series-store", "data"),
    State("symbol-dd", "value"),
    State("tf-dd", "value"),
    prevent_initial_call=True,
)
def live_tick(n, series, symbol, tf):
    if not series:
        return no_update, no_update, no_update, no_update, no_update

    try:
        # 1. Update last candle
        try:
            latest = _exchange.fetch_ohlcv(symbol, timeframe=tf, limit=2)
            if latest:
                ts, o, h, l, c, v = latest[-1]
                bar = {"time": int(ts / 1000), "open": float(o), "high": float(h),
                       "low": float(l), "close": float(c)}
                series = copy.deepcopy(series)
                price_data = series[0]["data"]
                if price_data and price_data[-1]["time"] == bar["time"]:
                    price_data[-1] = bar
                else:
                    price_data.append(bar)

                # volume
                if len(series) > 1 and series[1]["id"] == "volume":
                    color = "rgba(14,203,129,0.5)" if c >= o else "rgba(246,70,93,0.5)"
                    vol_pt = {"time": bar["time"], "value": float(v), "color": color}
                    vd = series[1]["data"]
                    if vd and vd[-1]["time"] == bar["time"]:
                        vd[-1] = vol_pt
                    else:
                        vd.append(vol_pt)
        except Exception as e:
            print(f"[live_tick candle] {e}")

        # 2. Order book + trades + ticker
        asks, bids = fetch_orderbook(symbol)
        trades = fetch_recent_trades(symbol)
        ticker = fetch_ticker(symbol)

        ob_panel = render_orderbook(asks, bids, ticker.get("last"))
        trades_panel = render_trades(trades)
        header = render_header(symbol, ticker)

        # Refresh open orders every few ticks
        open_orders_ui = _render_open_orders(symbol) if n % 4 == 0 else no_update

        return series, ob_panel, trades_panel, header, open_orders_ui

    except Exception as e:
        print(f"[live_tick] unexpected error: {e}")
        return no_update, no_update, no_update, no_update, no_update


# Buy / Sell tab switching
@callback(
    Output("tab-buy", "className"),
    Output("tab-sell", "className"),
    Output("submit-order", "children"),
    Output("submit-order", "className"),
    Output("side-store", "data"),
    Input("tab-buy", "n_clicks"),
    Input("tab-sell", "n_clicks"),
    State("side-store", "data"),
    prevent_initial_call=True,
)
def switch_side(buy_clicks, sell_clicks, current):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update, no_update
    btn = ctx.triggered[0]["prop_id"].split(".")[0]
    if btn == "tab-buy":
        return "side-btn active-buy", "side-btn", "Buy BTC", "btn-buy", "buy"
    else:
        return "side-btn", "side-btn active-sell", "Sell BTC", "btn-sell", "sell"


# Simple total calculation
@callback(
    Output("order-total", "value"),
    Input("order-price", "value"),
    Input("order-amount", "value"),
)
def calc_total(price, amount):
    if price and amount:
        return round(float(price) * float(amount), 2)
    return None


# Real / simulated order submit
@callback(
    Output("order-msg", "children"),
    Output("bottom-content", "children", allow_duplicate=True),
    Input("submit-order", "n_clicks"),
    State("side-store", "data"),
    State("order-type", "value"),
    State("order-price", "value"),
    State("order-amount", "value"),
    State("symbol-dd", "value"),
    prevent_initial_call=True,
)
def place_order(n, side, otype, price, amount, symbol):
    if not amount:
        return "Enter an amount", no_update

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "Invalid amount", no_update

    price_f = None
    if otype == "limit":
        if not price:
            return "Enter a price for limit order", no_update
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            return "Invalid price", no_update

    # For market orders the paper engine needs a reference price
    market_price = None
    if otype == "market":
        try:
            ticker = fetch_ticker(symbol)
            market_price = ticker.get("last")
        except Exception:
            market_price = price_f

    result = trader.place_order(
        symbol=symbol,
        side=side,
        order_type=otype,
        amount=amount,
        price=price_f,
        market_price=market_price,
    )

    # Refresh open-orders panel after a successful order
    open_orders_ui = no_update
    if result["success"]:
        open_orders_ui = _render_open_orders(symbol)

    color = "#0ecb81" if result["success"] else "#f6465d"
    msg = html.Span(result["message"], style={"color": color})
    return msg, open_orders_ui


def _render_open_orders(symbol: str):
    orders = trader.fetch_open_orders(symbol)
    if not orders:
        mode = trader.mode_label()
        return html.Div(
            f"No open orders ({mode} mode)",
            className="placeholder-msg",
        )

    rows = []
    for o in orders:
        rows.append(html.Tr([
            html.Td(o.get("id", "")[:10]),
            html.Td(o.get("side", "").upper()),
            html.Td(o.get("type", "")),
            html.Td(f"{o.get('price') or '—'}"),
            html.Td(f"{o.get('amount') or '—'}"),
            html.Td(o.get("status", "")),
            html.Td(
                html.Button("Cancel", id={"type": "cancel", "index": o.get("id")},
                            n_clicks=0, style={"fontSize": "11px", "cursor": "pointer"}),
            ),
        ]))

    return html.Table([
        html.Thead(html.Tr([
            html.Th("ID"), html.Th("Side"), html.Th("Type"),
            html.Th("Price"), html.Th("Amount"), html.Th("Status"), html.Th(""),
        ])),
        html.Tbody(rows),
    ], style={"width": "100%", "fontSize": "12px", "color": "#eaecef"})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8050))
    print("\n" + "=" * 60)
    print("  Binance-style Trading Interface")
    print(f"  → http://0.0.0.0:{port}")
    print("=" * 60 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
