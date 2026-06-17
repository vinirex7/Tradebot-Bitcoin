from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tradebot.allocation_signals import calculate_target_allocation
from tradebot.execution import live_market_buy, live_market_sell
from tradebot.indicators import enrich_indicators
from tradebot.state import append_jsonl, load_state, save_state


class AllocationStrategyEngine:
    def __init__(self, client, cfg: dict[str, Any]):
        self.client = client
        self.cfg = cfg
        self.symbol = cfg.get("exchange", {}).get("symbol", "BTCUSDT")
        self.mode = cfg.get("exchange", {}).get("mode", "paper")
        self.state_file = cfg.get("runtime", {}).get("state_file", "allocation_state.json")
        self.log_file = cfg.get("runtime", {}).get("log_file", "logs/allocation_decisions.jsonl")
        allocation = cfg.get("allocation", {})
        self.rebalance_threshold = float(allocation.get("rebalance_threshold", 0.10))
        self.min_trade_usdt = float(allocation.get("min_trade_usdt", 10.0))

    def run_once(self) -> dict[str, Any]:
        interval = self.cfg.get("historical_data", {}).get("interval", "1d")
        limit = self.cfg.get("historical_data", {}).get("limit", 1000)
        df = self.client.klines(self.symbol, interval=interval, limit=limit)
        df = enrich_indicators(df, self.cfg).dropna().reset_index(drop=True)

        state = load_state(self.state_file)
        if "allocation" not in state:
            state["allocation"] = {
                "paper_cash_usdt": float(state.get("paper_equity_usdt", 1000.0)),
                "paper_btc_qty": 0.0,
            }

        last = df.iloc[-1]
        price = float(last["close"])
        signal = calculate_target_allocation(df, self.cfg)

        alloc_state = state["allocation"]
        cash = float(alloc_state.get("paper_cash_usdt", 1000.0))
        btc_qty = float(alloc_state.get("paper_btc_qty", 0.0))
        equity = cash + btc_qty * price
        current_alloc = (btc_qty * price / equity) if equity > 0 else 0.0
        target_alloc = max(0.0, min(float(signal.target_allocation), 1.0))
        gap = target_alloc - current_alloc

        decision = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": self.symbol,
            "mode": self.mode,
            "price": price,
            "equity_usdt": equity,
            "current_allocation": current_alloc,
            "target_allocation": target_alloc,
            "regime": signal.regime,
            "reasons": signal.reasons,
            "action": "HOLD",
            "order": None,
        }

        if abs(gap) >= self.rebalance_threshold:
            target_btc_value = equity * target_alloc
            current_btc_value = btc_qty * price
            trade_value = target_btc_value - current_btc_value

            if trade_value > self.min_trade_usdt:
                quote_qty = min(trade_value, cash)
                if quote_qty > self.min_trade_usdt:
                    decision["action"] = "BUY"
                    if self.mode == "paper":
                        qty = quote_qty / price
                        cash -= quote_qty
                        btc_qty += qty
                        decision["order"] = {"mode": "paper", "side": "BUY", "quote_qty": quote_qty, "qty": qty}
                    else:
                        decision["order"] = live_market_buy(self.client, self.symbol, quote_qty)

            elif trade_value < -self.min_trade_usdt and btc_qty > 0:
                sell_value = min(abs(trade_value), btc_qty * price)
                qty_to_sell = min(btc_qty, sell_value / price)
                if qty_to_sell * price > self.min_trade_usdt:
                    decision["action"] = "SELL"
                    if self.mode == "paper":
                        cash += qty_to_sell * price
                        btc_qty -= qty_to_sell
                        decision["order"] = {"mode": "paper", "side": "SELL", "quote_qty": qty_to_sell * price, "qty": qty_to_sell}
                    else:
                        decision["order"] = live_market_sell(self.client, self.symbol, qty_to_sell)

        alloc_state["paper_cash_usdt"] = cash
        alloc_state["paper_btc_qty"] = btc_qty
        alloc_state["paper_equity_usdt"] = cash + btc_qty * price
        save_state(self.state_file, state)
        append_jsonl(self.log_file, decision)
        return decision
