import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(close, 12) - ema(close, 26)
    signal = ema(line, 9)
    hist = line - signal
    return line, signal, hist


def vol_adjusted_momentum(close: pd.Series, window: int) -> pd.Series:
    logret = np.log(close / close.shift(1))
    cumulative = logret.rolling(window).sum()
    volatility = logret.rolling(window).std() * np.sqrt(window)
    return cumulative / volatility.replace(0, np.nan)


def enrich_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    ind = cfg.get("indicators", {})
    close = out["close"]

    out["sma200d"] = sma(close, ind.get("sma_200d", 200))
    out["ema50d"] = ema(close, ind.get("ema_50d", 50))
    out["ema20d"] = ema(close, ind.get("ema_20d", 20))
    out["rsi14"] = rsi(close, ind.get("rsi_period", 14))
    out["atr14"] = atr(out, ind.get("atr_period", 14))
    out["atr_pct"] = out["atr14"] / out["close"]
    out["vol_ma20"] = out["volume"].rolling(ind.get("volume_ma", 20)).mean()

    macd_line, macd_signal, macd_hist = macd(close)
    out["macd"] = macd_line
    out["macd_signal"] = macd_signal
    out["macd_hist"] = macd_hist

    for w in ind.get("momentum_windows", [90, 180, 360]):
        out[f"m{w}"] = vol_adjusted_momentum(close, int(w))

    out["sma200d_slope20"] = out["sma200d"] - out["sma200d"].shift(20)
    out["dist_sma200d"] = (out["close"] / out["sma200d"]) - 1
    return out
