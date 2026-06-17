from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tradebot.indicators import enrich_indicators
from tradebot.regime import calculate_regime
from tradebot.risk import calculate_stop, position_size_usdt
from tradebot.signals import entry_signal, exit_signal


@dataclass
class BacktestResult:
    metrics: dict[str, Any]
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    decisions: pd.DataFrame


class Backtester:
    def __init__(self, cfg: dict[str, Any], raw_data: pd.DataFrame):
        self.cfg = cfg
        self.raw_data = raw_data.copy()
        bt = cfg.get("backtest", {})
        self.initial_capital = float(bt.get("initial_capital_usdt", 1000.0))
        self.fee_rate = float(bt.get("fee_rate", 0.001))
        self.slippage_rate = float(bt.get("slippage_rate", 0.0005))

    def run(self) -> BacktestResult:
        df = enrich_indicators(self.raw_data, self.cfg).dropna().reset_index(drop=True)
        if len(df) < 50:
            raise ValueError("Not enough data after indicator warmup")

        cash = self.initial_capital
        btc_qty = 0.0
        position = {
            "in_position": False,
            "entry_price": 0.0,
            "position_qty": 0.0,
            "position_usdt": 0.0,
            "peak_price": 0.0,
            "stop_price": 0.0,
            "take_profit_1_done": False,
            "take_profit_2_done": False,
            "entry_reason": "",
        }

        equity_rows: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []

        for i in range(370, len(df)):
            sub = df.iloc[: i + 1].copy()
            row = sub.iloc[-1]
            price = float(row["close"])
            ts = row.get("close_time", row.get("open_time", i))

            if position["in_position"]:
                position["peak_price"] = max(float(position.get("peak_price", price)), price)
                position["position_usdt"] = btc_qty * price

            equity = cash + btc_qty * price
            regime = calculate_regime(sub, self.cfg)

            action = "HOLD"
            reason = ""
            trade_row = None

            if position["in_position"]:
                signal = exit_signal(sub, position, self.cfg)
                action = signal.action
                reason = signal.reason
                if signal.action == "SELL":
                    qty_to_sell = btc_qty * float(signal.target_fraction)
                    if qty_to_sell > 0:
                        exec_price = price * (1 - self.slippage_rate)
                        gross = qty_to_sell * exec_price
                        fee = gross * self.fee_rate
                        net = gross - fee
                        cash += net
                        btc_qty -= qty_to_sell
                        pnl = (exec_price - float(position["entry_price"])) * qty_to_sell - fee
                        trade_row = {
                            "time": ts,
                            "side": "SELL",
                            "price": exec_price,
                            "qty": qty_to_sell,
                            "gross_usdt": gross,
                            "fee_usdt": fee,
                            "net_usdt": net,
                            "pnl_usdt": pnl,
                            "reason": reason,
                        }
                        trades.append(trade_row)
                        if btc_qty <= 1e-10 or signal.target_fraction >= 0.999:
                            btc_qty = 0.0
                            position.update({
                                "in_position": False,
                                "entry_price": 0.0,
                                "position_qty": 0.0,
                                "position_usdt": 0.0,
                                "peak_price": 0.0,
                                "stop_price": 0.0,
                                "entry_reason": "",
                            })
                        else:
                            position["position_qty"] = btc_qty
                            position["position_usdt"] = btc_qty * price
            else:
                signal = entry_signal(sub, regime, self.cfg)
                action = signal.action
                reason = signal.reason
                if signal.action == "BUY":
                    stop = calculate_stop(price, float(row["atr14"]), self.cfg)
                    target_equity = cash + btc_qty * price
                    size_usdt = position_size_usdt(target_equity, price, stop, signal.target_fraction, self.cfg)
                    size_usdt = min(size_usdt, cash)
                    if size_usdt > 10:
                        exec_price = price * (1 + self.slippage_rate)
                        fee = size_usdt * self.fee_rate
                        net_size = size_usdt - fee
                        qty = net_size / exec_price
                        cash -= size_usdt
                        btc_qty += qty
                        position.update({
                            "in_position": True,
                            "entry_price": exec_price,
                            "position_qty": btc_qty,
                            "position_usdt": btc_qty * exec_price,
                            "peak_price": exec_price,
                            "stop_price": stop,
                            "take_profit_1_done": False,
                            "take_profit_2_done": False,
                            "entry_reason": reason,
                        })
                        trade_row = {
                            "time": ts,
                            "side": "BUY",
                            "price": exec_price,
                            "qty": qty,
                            "gross_usdt": size_usdt,
                            "fee_usdt": fee,
                            "net_usdt": net_size,
                            "pnl_usdt": 0.0,
                            "reason": reason,
                        }
                        trades.append(trade_row)
                    else:
                        action = "HOLD"
                        reason = "position_size_below_minimum"

            equity = cash + btc_qty * price
            equity_rows.append({
                "time": ts,
                "close": price,
                "cash_usdt": cash,
                "btc_qty": btc_qty,
                "equity_usdt": equity,
                "drawdown": 0.0,
                "regime_score": regime.score,
                "regime": regime.regime,
            })
            decisions.append({
                "time": ts,
                "close": price,
                "action": action,
                "reason": reason,
                "regime_score": regime.score,
                "regime": regime.regime,
                "in_position": position["in_position"],
            })

        equity_curve = pd.DataFrame(equity_rows)
        if equity_curve.empty:
            raise ValueError("No backtest rows generated")
        peak = equity_curve["equity_usdt"].cummax()
        equity_curve["drawdown"] = equity_curve["equity_usdt"] / peak - 1

        trades_df = pd.DataFrame(trades)
        decisions_df = pd.DataFrame(decisions)
        metrics = self._metrics(equity_curve, trades_df, df)
        return BacktestResult(metrics=metrics, equity_curve=equity_curve, trades=trades_df, decisions=decisions_df)

    def _metrics(self, equity: pd.DataFrame, trades: pd.DataFrame, df: pd.DataFrame) -> dict[str, Any]:
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

        sells = trades[trades["side"] == "SELL"] if not trades.empty else pd.DataFrame()
        pnl = sells["pnl_usdt"] if not sells.empty and "pnl_usdt" in sells else pd.Series(dtype=float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        gross_profit = float(wins.sum()) if len(wins) else 0.0
        gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf if gross_profit > 0 else 0.0
        win_rate = len(wins) / len(pnl) if len(pnl) else 0.0

        buy_hold_start = float(df["close"].iloc[370])
        buy_hold_end = float(df["close"].iloc[-1])
        buy_hold_return = buy_hold_end / buy_hold_start - 1

        exposure_time = float((equity["btc_qty"] > 0).mean())

        return {
            "initial_capital_usdt": self.initial_capital,
            "start_equity_usdt": start_equity,
            "end_equity_usdt": end_equity,
            "total_return_pct": total_return * 100,
            "cagr_pct": cagr * 100,
            "max_drawdown_pct": max_dd * 100,
            "sharpe": sharpe,
            "sortino": sortino,
            "num_trades": int(len(trades)),
            "num_sells": int(len(sells)),
            "win_rate_pct": win_rate * 100,
            "profit_factor": profit_factor,
            "avg_win_usdt": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss_usdt": float(losses.mean()) if len(losses) else 0.0,
            "exposure_time_pct": exposure_time * 100,
            "buy_and_hold_return_pct": buy_hold_return * 100,
            "strategy_minus_buy_hold_pct": (total_return - buy_hold_return) * 100,
            "fee_rate": self.fee_rate,
            "slippage_rate": self.slippage_rate,
        }


def save_backtest_result(result: BacktestResult, output_dir: str | Path) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result.equity_curve.to_csv(out / "equity_curve.csv", index=False)
    result.trades.to_csv(out / "trades.csv", index=False)
    result.decisions.to_csv(out / "decisions.csv", index=False)
    pd.Series(result.metrics).to_json(out / "metrics.json", indent=2)
