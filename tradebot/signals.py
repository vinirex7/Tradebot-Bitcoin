from dataclasses import dataclass

import pandas as pd

from tradebot.regime import RegimeResult


@dataclass
class Signal:
    action: str
    strength: str
    reason: str
    target_fraction: float = 0.0


def _recent_high(df: pd.DataFrame, lookback: int) -> float:
    return float(df["high"].iloc[-lookback - 1 : -1].max())


def entry_signal(df: pd.DataFrame, regime: RegimeResult, cfg: dict) -> Signal:
    row = df.iloc[-1]
    prev = df.iloc[-2]
    entry_cfg = cfg.get("entry", {})
    risk_cfg = cfg.get("risk", {})

    close = float(row["close"])
    rsi14 = float(row.get("rsi14", 0) or 0)
    atr_pct = float(row.get("atr_pct", 1) or 1)
    m90 = float(row.get("m90", 0) or 0)
    m180 = float(row.get("m180", 0) or 0)
    sma200 = float(row.get("sma200d", 0) or 0)
    ema50 = float(row.get("ema50d", 0) or 0)
    ema20 = float(row.get("ema20d", 0) or 0)

    if regime.score < cfg.get("regime", {}).get("buy_threshold_reversal", 55):
        return Signal("HOLD", "none", "regime_score_too_low")
    if atr_pct > 0.09:
        return Signal("HOLD", "none", "volatility_too_high")
    if row.get("dist_sma200d", 0) > cfg.get("regime", {}).get("no_buy_if_distance_sma200d_above", 0.35):
        return Signal("HOLD", "none", "price_too_far_from_sma200d")

    reversal_breakout = close > _recent_high(df, entry_cfg.get("reversal_breakout_days", 7))
    rsi_cross_50 = prev.get("rsi14", 0) <= 50 and rsi14 > 50
    reversal_ok = (
        regime.regime == "reversal_accumulation"
        and close > ema50
        and m90 > 0
        and rsi14 > 50
        and reversal_breakout
    )
    if reversal_ok or (regime.regime == "reversal_accumulation" and rsi_cross_50 and close > ema50):
        return Signal(
            "BUY",
            "reversal",
            "reversal_entry_confirmed",
            min(entry_cfg.get("reversal_position_fraction", 0.25), risk_cfg.get("max_exposure", 0.60)),
        )

    breakout = close > _recent_high(df, entry_cfg.get("breakout_lookback_days", 20))
    volume_ok = row.get("volume", 0) > entry_cfg.get("breakout_volume_multiplier", 1.2) * row.get("vol_ma20", 10**99)
    trend_ok = (
        regime.score >= cfg.get("regime", {}).get("buy_threshold_trend", 70)
        and sma200 > 0
        and close > sma200
        and ema50 > sma200
        and m90 > 0
        and m180 > 0
        and 50 <= rsi14 <= 70
        and atr_pct < 0.06
    )
    pullback_ok = trend_ok and close >= ema20 and prev["close"] < prev.get("ema20d", prev["close"])
    breakout_ok = trend_ok and breakout and volume_ok and rsi14 < 75

    if pullback_ok:
        return Signal("BUY", "trend", "trend_pullback_entry", entry_cfg.get("trend_position_fraction", 0.50))
    if breakout_ok:
        return Signal("BUY", "trend", "trend_breakout_entry", entry_cfg.get("trend_position_fraction", 0.50))

    return Signal("HOLD", "none", "no_entry_signal")


def exit_signal(df: pd.DataFrame, position: dict, cfg: dict) -> Signal:
    if not position.get("in_position"):
        return Signal("HOLD", "none", "no_position")

    row = df.iloc[-1]
    close = float(row["close"])
    entry = float(position.get("entry_price", close))
    peak = max(float(position.get("peak_price", close)), close)
    stop_price = float(position.get("stop_price", entry * 0.90))

    m90 = float(row.get("m90", 0) or 0)
    sma200 = float(row.get("sma200d", 0) or 0)
    rsi14 = float(row.get("rsi14", 0) or 0)
    atr_pct = float(row.get("atr_pct", 0.05) or 0.05)

    if close <= stop_price:
        return Signal("SELL", "full", "stop_hit", 1.0)
    if close <= entry * (1 - cfg.get("exit", {}).get("hard_stop_pct", 0.12)):
        return Signal("SELL", "full", "hard_stop_hit", 1.0)
    if sma200 > 0 and close < sma200 and m90 < 0:
        return Signal("SELL", "full", "thesis_invalidated_sma200_m90", 1.0)

    if atr_pct < 0.04:
        trail = cfg.get("exit", {}).get("trailing_stop_low_vol", 0.08)
    elif atr_pct > 0.07:
        trail = cfg.get("exit", {}).get("trailing_stop_high_vol", 0.15)
    else:
        trail = cfg.get("exit", {}).get("trailing_stop_normal", 0.12)

    if peak > entry * 1.15 and close <= peak * (1 - trail):
        return Signal("SELL", "full", "trailing_stop_hit", 1.0)

    if rsi14 > 75 and row.get("dist_sma200d", 0) > 0.35:
        return Signal("SELL", "partial", "distribution_risk", 0.25)

    return Signal("HOLD", "none", "position_ok")
