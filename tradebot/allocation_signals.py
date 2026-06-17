from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class AllocationSignal:
    target_allocation: float
    regime: str
    reasons: list[str]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def calculate_target_allocation(df: pd.DataFrame, cfg: dict[str, Any]) -> AllocationSignal:
    """Modern Bitcoin regime allocation model.

    Instead of generating only BUY/SELL signals, this model estimates the target
    BTC allocation for the current regime. It is designed for the more mature
    Bitcoin market seen since 2020, where being structurally underexposed has
    often been more harmful than holding through normal volatility.
    """
    if len(df) < 370:
        return AllocationSignal(0.0, "warmup", ["not_enough_history"])

    row = df.iloc[-1]
    prev = df.iloc[-2]
    alloc_cfg = cfg.get("allocation", {})
    targets = alloc_cfg.get("targets", {})

    close = _safe_float(row.get("close"))
    sma200 = _safe_float(row.get("sma200d"))
    ema50 = _safe_float(row.get("ema50d"))
    ema20 = _safe_float(row.get("ema20d"))
    rsi14 = _safe_float(row.get("rsi14"))
    atr_pct = _safe_float(row.get("atr_pct"), 1.0)
    m90 = _safe_float(row.get("m90"))
    m180 = _safe_float(row.get("m180"))
    m360 = _safe_float(row.get("m360"))
    prev_m90 = _safe_float(prev.get("m90"))
    prev_m180 = _safe_float(prev.get("m180"))
    dist_sma200d = _safe_float(row.get("dist_sma200d"))

    recent_high_90 = _safe_float(df["close"].iloc[-90:].max(), close)
    recent_low_30 = _safe_float(df["close"].iloc[-30:].min(), close)
    drawdown_90 = close / recent_high_90 - 1 if recent_high_90 > 0 else 0.0

    bear_strong_target = float(targets.get("bear_strong", 0.00))
    bear_weakening_target = float(targets.get("bear_weakening", 0.20))
    accumulation_target = float(targets.get("accumulation", 0.35))
    bull_confirmed_target = float(targets.get("bull_confirmed", 0.70))
    strong_bull_target = float(targets.get("strong_bull", 0.85))
    euphoria_reduced_target = float(targets.get("euphoria_reduced", 0.60))
    neutral_target = float(targets.get("neutral", 0.20))

    max_target = float(alloc_cfg.get("max_allocation", 0.85))
    reasons: list[str] = []

    # Emergency/collapse regime.
    if drawdown_90 <= -0.30 and m90 < 0:
        return AllocationSignal(
            bear_strong_target,
            "collapse_defense",
            ["drawdown_90_below_30pct", "m90_negative"],
        )

    # Strong bear market: stay out.
    if close < sma200 and ema50 < sma200 and m180 < 0 and m360 < 0:
        return AllocationSignal(
            bear_strong_target,
            "bear_strong",
            ["close_below_sma200", "ema50_below_sma200", "m180_negative", "m360_negative"],
        )

    # Bear weakening: start small accumulation before classical confirmation.
    if close < sma200 and m90 > 0 and rsi14 > 45 and close > recent_low_30:
        return AllocationSignal(
            bear_weakening_target,
            "bear_weakening",
            ["close_below_sma200", "m90_positive", "rsi_above_45", "above_recent_low_30"],
        )

    # Recovery/accumulation.
    if close > ema50 and m90 > 0 and rsi14 > 50 and (m180 > prev_m180 or m180 > -0.25):
        # If the full bull regime is not confirmed yet, hold a medium allocation.
        if not (close > sma200 and ema50 > sma200 and m180 > 0):
            return AllocationSignal(
                accumulation_target,
                "accumulation_recovery",
                ["close_above_ema50", "m90_positive", "rsi_above_50", "m180_improving"],
            )

    # Euphoria / extended market.
    # Do not exit automatically. Reduce only if momentum is cooling and price loses EMA20.
    if dist_sma200d > 0.45 and rsi14 > 75:
        if m90 < prev_m90 and close < ema20:
            return AllocationSignal(
                euphoria_reduced_target,
                "euphoria_cooling",
                ["far_above_sma200", "rsi_above_75", "m90_cooling", "lost_ema20"],
            )
        return AllocationSignal(
            min(strong_bull_target, max_target),
            "euphoria_hold",
            ["far_above_sma200", "rsi_above_75", "trend_not_broken"],
        )

    # Strong bull market.
    if close > sma200 and ema50 > sma200 and m90 > m180 and m180 > 0 and m360 > 0 and 55 <= rsi14 <= 75 and atr_pct < 0.09:
        return AllocationSignal(
            min(strong_bull_target, max_target),
            "strong_bull",
            ["close_above_sma200", "ema50_above_sma200", "m90_above_m180", "m180_positive", "m360_positive", "rsi_55_75"],
        )

    # Confirmed bull market.
    if close > sma200 and ema50 > sma200 and m90 > 0 and m180 > 0 and rsi14 > 50:
        return AllocationSignal(
            min(bull_confirmed_target, max_target),
            "bull_confirmed",
            ["close_above_sma200", "ema50_above_sma200", "m90_positive", "m180_positive", "rsi_above_50"],
        )

    # Neutral but not dead. Keep a small allocation if long-term momentum is not broken.
    if m360 > 0 or close > sma200:
        return AllocationSignal(
            neutral_target,
            "neutral_structural",
            ["long_term_not_broken"],
        )

    return AllocationSignal(0.0, "defense", ["no_positive_regime"])
