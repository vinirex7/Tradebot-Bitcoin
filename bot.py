import argparse
import json
import time

from tradebot.binance_client import BinanceClient
from tradebot.config import load_config
from tradebot.strategy import BitcoinStrategyEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Vini BTC Regime Momentum Bot")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config file")
    parser.add_argument("--once", action="store_true", help="Run one decision cycle and exit")
    args = parser.parse_args()

    cfg = load_config(args.config)
    client = BinanceClient(cfg.get("exchange", {}).get("base_url"))
    engine = BitcoinStrategyEngine(client, cfg)
    minutes = int(cfg.get("loop", {}).get("decision_every_minutes", 15))

    while True:
        decision = engine.run_once()
        print(json.dumps(decision, indent=2, ensure_ascii=False))
        if args.once:
            break
        time.sleep(minutes * 60)


if __name__ == "__main__":
    main()
