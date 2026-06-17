from tradebot.binance_client import BinanceClient


def paper_buy(state: dict, price: float, size_usdt: float, stop_price: float, reason: str) -> dict:
    qty = size_usdt / price
    state["paper_equity_usdt"] = float(state.get("paper_equity_usdt", 1000.0))
    state["position"] = {
        "in_position": True,
        "entry_price": price,
        "position_qty": qty,
        "position_usdt": size_usdt,
        "peak_price": price,
        "stop_price": stop_price,
        "take_profit_1_done": False,
        "take_profit_2_done": False,
        "entry_reason": reason,
    }
    return {"mode": "paper", "side": "BUY", "price": price, "qty": qty, "quote_qty": size_usdt}


def paper_sell(state: dict, price: float, fraction: float, reason: str) -> dict:
    position = state["position"]
    qty_to_sell = position["position_qty"] * fraction
    usdt_value = qty_to_sell * price
    position["position_qty"] -= qty_to_sell
    position["position_usdt"] = position["position_qty"] * price
    if position["position_qty"] <= 1e-10 or fraction >= 0.999:
        position.update({
            "in_position": False,
            "entry_price": 0.0,
            "position_qty": 0.0,
            "position_usdt": 0.0,
            "peak_price": 0.0,
            "stop_price": 0.0,
            "entry_reason": "",
        })
    return {"mode": "paper", "side": "SELL", "price": price, "qty": qty_to_sell, "quote_qty": usdt_value, "reason": reason}


def live_market_buy(client: BinanceClient, symbol: str, quote_qty: float) -> dict:
    return client.market_buy_quote(symbol, quote_qty)


def live_market_sell(client: BinanceClient, symbol: str, qty: float) -> dict:
    return client.market_sell_qty(symbol, qty)
