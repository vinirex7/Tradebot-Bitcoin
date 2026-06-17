import pandas as pd

from tradebot.indicators import enrich_indicators


def test_enrich_indicators_creates_columns():
    rows = 420
    df = pd.DataFrame({
        "open": [100 + i for i in range(rows)],
        "high": [101 + i for i in range(rows)],
        "low": [99 + i for i in range(rows)],
        "close": [100 + i for i in range(rows)],
        "volume": [1000 for _ in range(rows)],
    })
    cfg = {"indicators": {"momentum_windows": [90, 180, 360]}}
    out = enrich_indicators(df, cfg)
    assert "sma200d" in out.columns
    assert "rsi14" in out.columns
    assert "atr_pct" in out.columns
    assert "m90" in out.columns
