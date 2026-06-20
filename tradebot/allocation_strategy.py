from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tradebot.allocation_signals import calculate_target_allocation
from tradebot.execution import live_market_buy, live_market_sell
from tradebot.indicators import enrich_indicators
from tradebot.state import append_jsonl, load_state, save_state


def _split_symbol(symbol: str) -> tuple[str, str]:
    known_quotes = ["USDT", "BUSD", "USDC", "FDUSD", "TUSD", "BTC", "ETH", "BNB"]
    for quote in known_quotes:
        if symbol.endswith(quote):
            return symbol[: -len(quote)], quote
    return symbol[:-4], symbol[-4:]


def _asset_free_balance(account: dict[str, Any], asset: str) -> float:
    for bal in account.get("balances", []):
        if bal.get("asset") == asset:
            return float(bal.get("free", 0.0))
    return 0.0


def _order_executed_qty(order: dict[str, Any]) -> float:
    return float(order.get("executedQty", 0.0) or 0.0)


def _order_quote_spent(order: dict[str, Any]) -> float:
    return float(order.get("cummulativeQuoteQty", 0.0) or 0.0)


class AllocationStrategyEngine:
    def __init__(self, client, cfg: dict[str, Any]):
        self.client = client
        self.cfg = cfg
        self.symbol = cfg.get("exchange", {}).get("symbol", "BTCUSDT")
        self.mode = cfg.get("exchange", {}).get("mode", "paper")
        self.base_asset, self.quote_asset = _split_symbol(self.symbol)

        self.state_file = cfg.get("runtime", {}).get("state_file", "allocation_state.json")
        self.log_file = cfg.get("runtime", {}).get("log_file", "logs/allocation_decisions.jsonl")

        allocation = cfg.get("allocation", {})
        self.rebalance_threshold = float(allocation.get("rebalance_threshold", 0.10))
        self.min_trade_usdt = float(allocation.get("min_trade_usdt", 10.0))

        live_cfg = cfg.get("live", {})
        self.max_capital_usdt = float(live_cfg.get("max_capital_usdt", 0.0))
        self.dry_run = bool(live_cfg.get("dry_run", False))

    def run_once(self) -> dict[str, Any]:
        interval = self.cfg.get("historical_data", {}).get("interval", "1d")
        limit = self.cfg.get("historical_data", {}).get("limit", 1000)

        df = self.client.klines(self.symbol, interval=interval, limit=limit)
        df = enrich_indicators(df, self.cfg).dropna().reset_index(drop=True)

        last = df.iloc[-1]
        price = float(last["close"])
        signal = calculate_target_allocation(df, self.cfg)

        state = load_state(self.state_file)
        if "allocation" not in state:
            state["allocation"] = {}

        alloc_state = state["allocation"]

        free_quote = 0.0
        free_base = 0.0
        actual_equity = 0.0

        if self.mode == "paper":
            cash = float(alloc_state.get("paper_cash_usdt", float(state.get("paper_equity_usdt", 1000.0))))
            base_qty = float(alloc_state.get("paper_btc_qty", 0.0))
            usable_capital = cash + base_qty * price
            equity = usable_capital

        else:
            if self.max_capital_usdt <= 0:
                raise RuntimeError("live.max_capital_usdt must be greater than 0 in live mode")

            # In live mode, balances must come from Binance on every cycle.
            # State is only telemetry; it must never be the source of truth for equity.
            account = self.client.account()
            free_quote = _asset_free_balance(account, self.quote_asset)
            free_base = _asset_free_balance(account, self.base_asset)
            actual_equity = free_quote + free_base * price

            usable_capital = min(self.max_capital_usdt, actual_equity)
            cash = min(free_quote, usable_capital)

            max_base_qty_in_scope = max(0.0, usable_capital - cash) / price if price > 0 else 0.0
            base_qty = min(free_base, max_base_qty_in_scope)
            equity = usable_capital

        current_alloc = (base_qty * price / equity) if equity > 0 else 0.0
        target_alloc = max(0.0, min(float(signal.target_allocation), 1.0))
        gap = target_alloc - current_alloc

        decision = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": self.symbol,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "price": price,
            "equity_usdt": equity,
            "usable_capital_usdt": usable_capital,
            "max_capital_usdt": self.max_capital_usdt if self.mode != "paper" else None,
            "actual_equity_usdt": actual_equity if self.mode != "paper" else equity,
            "free_quote": free_quote if self.mode != "paper" else cash,
            "free_base": free_base if self.mode != "paper" else base_qty,
            "current_allocation": current_alloc,
            "target_allocation": target_alloc,
            "regime": signal.regime,
            "reasons": signal.reasons,
            "action": "HOLD",
            "order": None,
        }

        if usable_capital < self.min_trade_usdt:
            decision["action"] = "HOLD"
            decision["order"] = None
            decision["reason"] = "usable_capital_below_min_trade"
            if self.mode != "paper":
                alloc_state["live_cash_usdt"] = free_quote
                alloc_state["live_base_qty"] = free_base
                alloc_state["live_equity_usdt"] = actual_equity
                alloc_state["live_usable_capital_usdt"] = usable_capital
            save_state(self.state_file, state)
            append_jsonl(self.log_file, decision)
            return decision

        if abs(gap) >= self.rebalance_threshold:
            target_base_value = usable_capital * target_alloc
            current_base_value = base_qty * price
            trade_value = target_base_value - current_base_value

            if trade_value > self.min_trade_usdt:
                quote_qty = min(trade_value, cash, usable_capital)

                if quote_qty > self.min_trade_usdt:
                    decision["action"] = "BUY"

                    if self.mode == "paper":
                        qty = quote_qty / price
                        cash -= quote_qty
                        base_qty += qty
                        decision["order"] = {
                            "mode": self.mode,
                            "dry_run": self.dry_run,
                            "side": "BUY",
                            "quote_qty": quote_qty,
                            "qty": qty,
                        }
                    elif self.dry_run:
                        decision["order"] = {
                            "mode": self.mode,
                            "dry_run": self.dry_run,
                            "side": "BUY",
                            "quote_qty": quote_qty,
                            "qty": quote_qty / price,
                            "note": "dry_run_no_order_sent",
                        }
                    else:
                        order = live_market_buy(self.client, self.symbol, quote_qty)
                        executed_qty = _order_executed_qty(order)
                        quote_spent = _order_quote_spent(order)

                        if executed_qty > 0:
                            base_qty += executed_qty
                            cash = max(0.0, cash - quote_spent)

                        decision["order"] = order

            elif trade_value < -self.min_trade_usdt and base_qty > 0:
                sell_value = min(abs(trade_value), base_qty * price)
                qty_to_sell = min(base_qty, sell_value / price)

                if qty_to_sell * price > self.min_trade_usdt:
                    decision["action"] = "SELL"

                    if self.mode == "paper":
                        cash += qty_to_sell * price
                        base_qty -= qty_to_sell
                        decision["order"] = {
                            "mode": self.mode,
                            "dry_run": self.dry_run,
                            "side": "SELL",
                            "quote_qty": qty_to_sell * price,
                            "qty": qty_to_sell,
                        }
                    elif self.dry_run:
                        decision["order"] = {
                            "mode": self.mode,
                            "dry_run": self.dry_run,
                            "side": "SELL",
                            "quote_qty": qty_to_sell * price,
                            "qty": qty_to_sell,
                            "note": "dry_run_no_order_sent",
                        }
                    else:
                        order = live_market_sell(self.client, self.symbol, qty_to_sell)
                        executed_qty = _order_executed_qty(order)
                        quote_received = _order_quote_spent(order)

                        if executed_qty > 0:
                            base_qty = max(0.0, base_qty - executed_qty)
                            cash += quote_received

                        decision["order"] = order

        if self.mode == "paper":
            alloc_state["paper_cash_usdt"] = cash
            alloc_state["paper_btc_qty"] = base_qty
            alloc_state["paper_equity_usdt"] = cash + base_qty * price
        else:
            alloc_state["live_cash_usdt"] = free_quote
            alloc_state["live_base_qty"] = free_base
            alloc_state["live_equity_usdt"] = actual_equity
            alloc_state["live_usable_capital_usdt"] = usable_capital

        save_state(self.state_file, state)
        append_jsonl(self.log_file, decision)
        return decision
