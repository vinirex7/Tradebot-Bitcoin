def calculate_stop(entry_price: float, atr: float, cfg: dict) -> float:
    exit_cfg = cfg.get("exit", {})
    risk_cfg = cfg.get("risk", {})
    atr_stop = entry_price - exit_cfg.get("initial_stop_atr_multiplier", 2.5) * atr
    pct_stop = entry_price * (1 - exit_cfg.get("default_stop_pct", 0.10))
    stop = min(atr_stop, pct_stop)

    max_stop = entry_price * (1 - risk_cfg.get("max_stop_distance", 0.15))
    min_stop = entry_price * (1 - risk_cfg.get("min_stop_distance", 0.06))
    return max(max_stop, min(stop, min_stop))


def position_size_usdt(equity_usdt: float, entry_price: float, stop_price: float, target_fraction: float, cfg: dict) -> float:
    risk_cfg = cfg.get("risk", {})
    risk_amount = equity_usdt * risk_cfg.get("risk_per_trade", 0.0075)
    stop_distance = max((entry_price - stop_price) / entry_price, 0.0001)
    size_by_risk = risk_amount / stop_distance
    size_by_regime = equity_usdt * target_fraction
    max_exposure = equity_usdt * risk_cfg.get("max_exposure", 0.60)
    return max(0.0, min(size_by_risk, size_by_regime, max_exposure))
