def calculate_stop(entry_price: float, atr: float, cfg: dict) -> float:
    exit_cfg = cfg.get("exit", {})
    risk_cfg = cfg.get("risk", {})

    atr_stop = entry_price - exit_cfg.get("initial_stop_atr_multiplier", 2.5) * atr
    pct_stop = entry_price * (1 - exit_cfg.get("default_stop_pct", 0.10))

    stop = min(atr_stop, pct_stop)

    max_stop = entry_price * (1 - risk_cfg.get("max_stop_distance", 0.15))
    min_stop = entry_price * (1 - risk_cfg.get("min_stop_distance", 0.06))

    return max(max_stop, min(stop, min_stop))


def position_size_usdt(
    equity_usdt: float,
    entry_price: float,
    stop_price: float,
    target_fraction: float,
    cfg: dict,
) -> float:
    """
    V3: tamanho da posição por alocação de regime.

    Reversão inicial: geralmente 25% da banca.
    Tendência confirmada: geralmente 50% da banca.
    Limite máximo: definido por max_exposure.

    O stop ainda existe para saída, mas não reduz demais a entrada.
    """

    risk_cfg = cfg.get("risk", {})

    max_exposure = risk_cfg.get("max_exposure", 0.60)

    size_by_regime = equity_usdt * target_fraction
    max_size = equity_usdt * max_exposure

    size = min(size_by_regime, max_size)

    return max(0.0, size)