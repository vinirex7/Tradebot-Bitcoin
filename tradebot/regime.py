from dataclasses import dataclass

import pandas as pd


@dataclass
class RegimeResult:
    score: int
    regime: str
    reasons: list[str]


def calculate_regime(df: pd.DataFrame, cfg: dict) -> RegimeResult:
    row = df.iloc[-1]
    score = 0
    reasons: list[str] = []

    close = float(row["close"])
    sma200 = float(row.get("sma200d", 0) or 0)
    ema50 = float(row.get("ema50d", 0) or 0)
    m90 = float(row.get("m90", 0) or 0)
    m180 = float(row.get("m180", 0) or 0)
    rsi14 = float(row.get("rsi14", 0) or 0)
    atr_pct = float(row.get("atr_pct", 1) or 1)
    macd = float(row.get("macd", 0) or 0)
    macd_signal = float(row.get("macd_signal", 0) or 0)
    dist_sma200d = float(row.get("dist_sma200d", 0) or 0)
    slope20 = float(row.get("sma200d_slope20", 0) or 0)

    if sma200 and close > sma200:
        score += 15
        reasons.append("close_above_sma200d")
    if slope20 > 0:
        score += 10
        reasons.append("sma200d_rising")
    if sma200 and ema50 > sma200:
        score += 10
        reasons.append("ema50_above_sma200d")
    if m90 > 0:
        score += 10
        reasons.append("m90_positive")
    if m180 > 0:
        score += 10
        reasons.append("m180_positive")
    if m90 > m180:
        score += 5
        reasons.append("momentum_accelerating")
    if macd > macd_signal:
        score += 5
        reasons.append("macd_above_signal")
    if 50 <= rsi14 <= 70:
        score += 5
        reasons.append("rsi_healthy")
    if atr_pct < 0.06:
        score += 5
        reasons.append("volatility_ok")
    if row.get("volume", 0) > row.get("vol_ma20", 10**99):
        score += 5
        reasons.append("volume_above_average")

    if sma200 and close < sma200:
        score -= 15
        reasons.append("penalty_close_below_sma200d")
    if m90 < 0:
        score -= 10
        reasons.append("penalty_m90_negative")
    if m180 < 0:
        score -= 10
        reasons.append("penalty_m180_negative")
    if dist_sma200d > cfg.get("regime", {}).get("no_buy_if_distance_sma200d_above", 0.35):
        score -= 10
        reasons.append("penalty_too_far_from_sma200d")

    score = max(0, min(100, int(score)))

    if score < 40:
        regime = "bear_defense"
    elif score < 55:
        regime = "neutral"
    elif score < 70:
        regime = "reversal_accumulation"
    elif score < 85:
        regime = "bull_confirmed"
    else:
        regime = "strong_bull_watch_top"

    return RegimeResult(score=score, regime=regime, reasons=reasons)
