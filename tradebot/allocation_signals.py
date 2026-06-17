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


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _volatility_adjusted_target(target: float, atr_pct: float, alloc_cfg: dict[str, Any], reasons: list[str]) -> float:
    vol_cfg = alloc_cfg.get("volatility_scaling", {})
    if not bool(vol_cfg.get("enabled", True)):
        return target

    high_atr_pct = float(vol_cfg.get("high_atr_pct", 0.08))
    extreme_atr_pct = float(vol_cfg.get("extreme_atr_pct", 0.11))
    high_multiplier = float(vol_cfg.get("high_multiplier", 0.75))
    extreme_multiplier = float(vol_cfg.get("extreme_multiplier", 0.55))

    if atr_pct >= extreme_atr_pct:
        reasons.append("volatility_extreme_target_reduced")
        return target * extreme_multiplier

    if atr_pct >= high_atr_pct:
        reasons.append("volatility_high_target_reduced")
        return target * high_multiplier

    return target


def _final_signal(target: float, regime: str, reasons: list[str], atr_pct: float, alloc_cfg: dict[str, Any]) -> AllocationSignal:
    max_target = float(alloc_cfg.get("max_allocation", 0.85))
    adjusted = _volatility_adjusted_target(target, atr_pct, alloc_cfg, reasons)
    return AllocationSignal(_clamp(adjusted, 0.0, max_target), regime, reasons)


def calculate_target_allocation(df: pd.DataFrame, cfg: dict[str, Any]) -> AllocationSignal:
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
    sma200_slope20 = _safe_float(row.get("sma200d_slope20"))
    sma200_slope20_pct = sma200_slope20 / sma200 if sma200 > 0 else 0.0

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
    chop_target = float(targets.get("chop", neutral_target))

    if drawdown_90 <= -0.30 and m90 < 0:
        return _final_signal(
            bear_strong_target,
            "collapse_defense",
            ["drawdown_90_below_30pct", "m90_negative"],
            atr_pct,
            alloc_cfg,
        )

    if close < sma200 and ema50 < sma200 and m180 < 0 and m360 < 0:
        return _final_signal(
            bear_strong_target,
            "bear_strong",
            ["close_below_sma200", "ema50_below_sma200", "m180_negative", "m360_negative"],
            atr_pct,
            alloc_cfg,
        )

    if close < sma200 and m90 > 0 and rsi14 > 45 and close > recent_low_30:
        return _final_signal(
            bear_weakening_target,
            "bear_weakening",
            ["close_below_sma200", "m90_positive", "rsi_above_45", "above_recent_low_30"],
            atr_pct,
            alloc_cfg,
        )

    chop_cfg = alloc_cfg.get("chop_filter", {})
    if bool(chop_cfg.get("enabled", True)):
        chop_dist = float(chop_cfg.get("max_abs_dist_sma200d", 0.06))
        chop_m90 = float(chop_cfg.get("max_abs_m90", 0.25))
        chop_slope = float(chop_cfg.get("max_abs_sma200_slope20_pct", 0.015))
        rsi_low = float(chop_cfg.get("rsi_low", 45))
        rsi_high = float(chop_cfg.get("rsi_high", 55))

        is_chop = (
            abs(dist_sma200d) <= chop_dist
            and abs(m90) <= chop_m90
            and abs(sma200_slope20_pct) <= chop_slope
            and rsi_low <= rsi14 <= rsi_high
        )

        if is_chop:
            return _final_signal(
                chop_target,
                "chop_sideways",
                ["near_sma200", "m90_flat", "sma200_slope_flat", "rsi_mid_range"],
                atr_pct,
                alloc_cfg,
            )

    if close > ema50 and m90 > 0 and rsi14 > 50 and (m180 > prev_m180 or m180 > -0.25):
        if not (close > sma200 and ema50 > sma200 and m180 > 0):
            return _final_signal(
                accumulation_target,
                "accumulation_recovery",
                ["close_above_ema50", "m90_positive", "rsi_above_50", "m180_improving"],
                atr_pct,
                alloc_cfg,
            )

    if dist_sma200d > 0.45 and rsi14 > 75:
        if m90 < prev_m90 and close < ema20:
            return _final_signal(
                euphoria_reduced_target,
                "euphoria_cooling",
                ["far_above_sma200", "rsi_above_75", "m90_cooling", "lost_ema20"],
                atr_pct,
                alloc_cfg,
            )

        return _final_signal(
            strong_bull_target,
            "euphoria_hold",
            ["far_above_sma200", "rsi_above_75", "trend_not_broken"],
            atr_pct,
            alloc_cfg,
        )

    if close > sma200 and ema50 > sma200 and m90 > m180 and m180 > 0 and m360 > 0 and 55 <= rsi14 <= 75 and atr_pct < 0.09:
        return _final_signal(
            strong_bull_target,
            "strong_bull",
            ["close_above_sma200", "ema50_above_sma200", "m90_above_m180", "m180_positive", "m360_positive", "rsi_55_75"],
            atr_pct,
            alloc_cfg,
        )

    if close > sma200 and ema50 > sma200 and m90 > 0 and m180 > 0 and rsi14 > 50:
        return _final_signal(
            bull_confirmed_target,
            "bull_confirmed",
            ["close_above_sma200", "ema50_above_sma200", "m90_positive", "m180_positive", "rsi_above_50"],
            atr_pct,
            alloc_cfg,
        )

    if m360 > 0 or close > sma200:
        return _final_signal(
            neutral_target,
            "neutral_structural",
            ["long_term_not_broken"],
            atr_pct,
            alloc_cfg,
        )

    return _final_signal(0.0, "defense", ["no_positive_regime"], atr_pct, alloc_cfg)