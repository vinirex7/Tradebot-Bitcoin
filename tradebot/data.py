from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests


BASE_URL = "https://api.binance.com"


def _to_milliseconds(value: str | None) -> int | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_binance_klines(
    symbol: str,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
    base_url: str = BASE_URL,
) -> pd.DataFrame:
    """Download historical klines from Binance public REST API.

    Binance returns a maximum of 1000 candles per request, so this function
    paginates until the requested end date or until no more data is returned.
    """
    start_ms = _to_milliseconds(start)
    end_ms = _to_milliseconds(end)
    rows: list[list] = []

    while True:
        params = {"symbol": symbol, "interval": interval, "limit": 1000}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms

        resp = requests.get(f"{base_url.rstrip('/')}/api/v3/klines", params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        rows.extend(batch)
        last_close = int(batch[-1][6])
        next_start = last_close + 1
        if start_ms is not None and next_start <= start_ms:
            break
        start_ms = next_start
        if len(batch) < 1000:
            break
        if end_ms is not None and start_ms >= end_ms:
            break

    cols = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_base", "taker_quote", "ignore"
    ]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_base", "taker_quote"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
    return df
