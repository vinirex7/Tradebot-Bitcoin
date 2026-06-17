from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tradebot.allocation_signals import calculate_target_allocation
from tradebot.indicators import enrich_indicators


@dataclass
class AllocationBacktestResult:
    metrics: dict[str, Any]
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    decisions: pd.DataFrame


class AllocationBacktester:
    def __init__(self, cfg: dict[str, Any], raw_data: pd.DataFrame):
        self.cfg = cfg
        self.raw_data = raw_data.copy()
        bt = cfg.get("backtest", {})
        self.initial_capital = float(bt.get("initial_capital_usdt", 1000.0))
        self.fee_rate = float(bt.get("fee_rate", 0.001))
        self.slippage_rate = float(bt.get("slippage_rate", 0.0005))
        allocation = cfg.get("allocation", {})
        self.rebalance_threshold = float(allocation.get("rebalance_threshold", 0.10))
        self.min_trade_usdt = float(allocation.get("min_trade_usdt", 10.0))

    def run(self) -> AllocationBacktestResult:
        df = enrich_indicators(self.raw_data, self.cfg).dropna().reset_index(drop=True)
        if len(df) < 400:
            raise ValueError("Not enough data after indicator warmup")

        cash = self.initial_capital
        btc_qty = 0.0
        equity_rows: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []

        # Warmup keeps the long indicators realistic.
        warmup = int(self.cfg.get("backtest", {}).get("warmup_candles", 370))

        for i in range(warmup, len(df)):
            sub = df.iloc[: i + 1].copy()
            row = sub.iloc[-1]
            price = float(row["close"])
            ts = row.get("close_time", row.get("open_time", i))

            equity_before = cash + btc_qty * price
            if equity_before <= 0:
                break

            current_btc_value = btc_qty * price
            current_alloc = current_btc_value / equity_before
            signal = calculate_target_allocation(sub, self.cfg)
            target_alloc = max(0.0, min(float(signal.target_allocation), 1.0))
            allocation_gap = target_alloc - current_alloc

            action = "HOLD"
            trade_row = None

            if abs(allocation_gap) >= self.rebalance_threshold:
                target_btc_value = equity_before * target_alloc
                trade_value = target_btc_value - current_btc_value

                if trade_value > self.min_trade_usdt and cash > self.min_trade_usdt:
                    spend = min(trade_value, cash)
                    exec_price = price * (1 + self.slippage_rate)
                    fee = spend * self.fee_rate
                    net_spend = spend - fee
                    qty = net_spend / exec_price
                    cash -= spend
                    btc_qty += qty
                    action = "BUY"
                    trade_row = {
                        "time": ts,
                        "side": "BUY",
                        "price": exec_price,
                        "qty": qty,
                        "gross_usdt": spend,
                        "fee_usdt": fee,
                        "net_usdt": net_spend,
                        "reason": signal.regime,
                        "target_allocation": target_alloc,
                        "current_allocation_before": current_alloc,
                    }
                    trades.append(trade_row)

                elif trade_value < -self.min_trade_usdt and btc_qty > 0:
                    sell_value = min(abs(trade_value), current_btc_value)
                    qty_to_sell = min(btc_qty, sell_value / price)
                    if qty_to_sell * price > self.min_trade_usdt:
                        exec_price = price * (1 - self.slippage_rate)
                        gross = qty_to_sell * exec_price
                        fee = gross * self.fee_rate
                        net = gross - fee
                        cash += net
                        btc_qty -= qty_to_sell
                        action = "SELL"
                        trade_row = {
                            "time": ts,
                            "side": "SELL",
                            "price": exec_price,
                            "qty": qty_to_sell,
                            "gross_usdt": gross,
                            "fee_usdt": fee,
                            "net_usdt": net,
                            "reason": signal.regime,
                            "target_allocation": target_alloc,
                            "current_allocation_before": current_alloc,
                        }
                        trades.append(trade_row)

            equity_after = cash + btc_qty * price
            btc_value_after = btc_qty * price
            allocation_after = btc_value_after / equity_after if equity_after > 0 else 0.0

            equity_rows.append({
                "time": ts,
                "close": price,
                "cash_usdt": cash,
                "btc_qty": btc_qty,
                "btc_value_usdt": btc_value_after,
                "equity_usdt": equity_after,
                "btc_allocation": allocation_after,
                "target_allocation": target_alloc,
                "drawdown": 0.0,
                "regime": signal.regime,
            })
            decisions.append({
                "time": ts,
                "close": price,
                "action": action,
                "regime": signal.regime,
                "reasons": "|".join(signal.reasons),
                "target_allocation": target_alloc,
                "current_allocation_before": current_alloc,
                "allocation_after": allocation_after,
            })

        equity_curve = pd.DataFrame(equity_rows)
        if equity_curve.empty:
            raise ValueError("No backtest rows generated")
        peak = equity_curve["equity_usdt"].cummax()
        equity_curve["drawdown"] = equity_curve["equity_usdt"] / peak - 1

        trades_df = pd.DataFrame(trades)
        decisions_df = pd.DataFrame(decisions)
        metrics = self._metrics(equity_curve, trades_df, df, warmup)
        return AllocationBacktestResult(metrics, equity_curve, trades_df, decisions_df)

    def _metrics(self, equity: pd.DataFrame, trades: pd.DataFrame, df: pd.DataFrame, warmup: int) -> dict[str, Any]:
        start_equity = float(equity["equity_usdt"].iloc[0])
        end_equity = float(equity["equity_usdt"].iloc[-1])
        total_return = end_equity / start_equity - 1
        daily_returns = equity["equity_usdt"].pct_change().dropna()

        days = max((pd.to_datetime(equity["time"].iloc[-1]) - pd.to_datetime(equity["time"].iloc[0])).days, 1)
        years = days / 365.25
        cagr = (end_equity / start_equity) ** (1 / years) - 1 if years > 0 else np.nan
        max_dd = float(equity["drawdown"].min())
        sharpe = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(365)) if daily_returns.std() != 0 else 0.0
        downside = daily_returns[daily_returns < 0]
        sortino = float((daily_returns.mean() / downside.std()) * np.sqrt(365)) if len(downside) > 1 and downside.std() != 0 else 0.0

        buy_hold_start = float(df["close"].iloc[warmup])
        buy_hold_end = float(df["close"].iloc[-1])
        buy_hold_return = buy_hold_end / buy_hold_start - 1

        num_buys = int((trades["side"] == "BUY").sum()) if not trades.empty and "side" in trades else 0
        num_sells = int((trades["side"] == "SELL").sum()) if not trades.empty and "side" in trades else 0
        exposure_time = float((equity["btc_allocation"] > 0.05).mean())
        avg_allocation = float(equity["btc_allocation"].mean())
        avg_target = float(equity["target_allocation"].mean())

        return {
            "strategy": "btc_modern_regime_allocation_v1",
            "initial_capital_usdt": self.initial_capital,
            "start_equity_usdt": start_equity,
            "end_equity_usdt": end_equity,
            "total_return_pct": total_return * 100,
            "cagr_pct": cagr * 100,
            "max_drawdown_pct": max_dd * 100,
            "sharpe": sharpe,
            "sortino": sortino,
            "num_trades": int(len(trades)),
            "num_buys": num_buys,
            "num_sells": num_sells,
            "exposure_time_pct": exposure_time * 100,
            "average_btc_allocation_pct": avg_allocation * 100,
            "average_target_allocation_pct": avg_target * 100,
            "buy_and_hold_return_pct": buy_hold_return * 100,
            "strategy_minus_buy_hold_pct": (total_return - buy_hold_return) * 100,
            "fee_rate": self.fee_rate,
            "slippage_rate": self.slippage_rate,
            "rebalance_threshold": self.rebalance_threshold,
        }


def save_allocation_backtest_result(result: AllocationBacktestResult, output_dir: str | Path) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result.equity_curve.to_csv(out / "equity_curve.csv", index=False)
    result.trades.to_csv(out / "trades.csv", index=False)
    result.decisions.to_csv(out / "decisions.csv", index=False)
    pd.Series(result.metrics).to_json(out / "metrics.json", indent=2)
