from datetime import datetime, timezone

from tradebot.execution import live_market_buy, live_market_sell, paper_buy, paper_sell
from tradebot.indicators import enrich_indicators
from tradebot.regime import calculate_regime
from tradebot.risk import calculate_stop, position_size_usdt
from tradebot.signals import entry_signal, exit_signal
from tradebot.state import append_jsonl, load_state, save_state


class BitcoinStrategyEngine:
    def __init__(self, client, cfg: dict):
        self.client = client
        self.cfg = cfg
        self.symbol = cfg.get("exchange", {}).get("symbol", "BTCUSDT")
        self.mode = cfg.get("exchange", {}).get("mode", "paper")
        self.state_file = cfg.get("runtime", {}).get("state_file", "state.json")
        self.log_file = cfg.get("runtime", {}).get("log_file", "logs/decisions.jsonl")

    def run_once(self) -> dict:
        interval = self.cfg.get("historical_data", {}).get("interval", "1d")
        limit = self.cfg.get("historical_data", {}).get("limit", 1000)
        df = self.client.klines(self.symbol, interval=interval, limit=limit)
        df = enrich_indicators(df, self.cfg).dropna().reset_index(drop=True)

        state = load_state(self.state_file)
        position = state.get("position", {})
        last = df.iloc[-1]
        price = float(last["close"])

        if position.get("in_position"):
            position["peak_price"] = max(float(position.get("peak_price", price)), price)

        regime = calculate_regime(df, self.cfg)
        decision = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": self.symbol,
            "mode": self.mode,
            "price": price,
            "regime_score": regime.score,
            "regime": regime.regime,
            "regime_reasons": regime.reasons,
            "action": "HOLD",
            "reason": "",
            "order": None,
        }

        if position.get("in_position"):
            signal = exit_signal(df, position, self.cfg)
            decision.update({"action": signal.action, "reason": signal.reason})
            if signal.action == "SELL":
                if self.mode == "paper":
                    decision["order"] = paper_sell(state, price, signal.target_fraction, signal.reason)
                else:
                    qty = float(position.get("position_qty", 0.0)) * signal.target_fraction
                    decision["order"] = live_market_sell(self.client, self.symbol, qty)
        else:
            signal = entry_signal(df, regime, self.cfg)
            decision.update({"action": signal.action, "reason": signal.reason})
            if signal.action == "BUY":
                equity = float(state.get("paper_equity_usdt", 1000.0))
                stop = calculate_stop(price, float(last["atr14"]), self.cfg)
                size = position_size_usdt(equity, price, stop, signal.target_fraction, self.cfg)
                if size > 10:
                    if self.mode == "paper":
                        decision["order"] = paper_buy(state, price, size, stop, signal.reason)
                    else:
                        decision["order"] = live_market_buy(self.client, self.symbol, size)
                else:
                    decision.update({"action": "HOLD", "reason": "position_size_below_minimum"})

        save_state(self.state_file, state)
        append_jsonl(self.log_file, decision)
        return decision
