import pandas as pd

from tradebot.allocation_signals import calculate_target_allocation
from tradebot.indicators import enrich_indicators


def test_allocation_signal_returns_valid_target():
    rows = 430
    df = pd.DataFrame({
        "open": [100 + i for i in range(rows)],
        "high": [101 + i for i in range(rows)],
        "low": [99 + i for i in range(rows)],
        "close": [100 + i for i in range(rows)],
        "volume": [1000 for _ in range(rows)],
    })
    cfg = {
        "indicators": {"momentum_windows": [90, 180, 360]},
        "allocation": {
            "max_allocation": 0.85,
            "targets": {
                "bear_strong": 0.0,
                "bear_weakening": 0.2,
                "neutral": 0.2,
                "accumulation": 0.35,
                "bull_confirmed": 0.7,
                "strong_bull": 0.85,
                "euphoria_reduced": 0.6,
            },
        },
    }
    enriched = enrich_indicators(df, cfg).dropna().reset_index(drop=True)
    signal = calculate_target_allocation(enriched, cfg)
    assert 0 <= signal.target_allocation <= 1
    assert signal.regime
