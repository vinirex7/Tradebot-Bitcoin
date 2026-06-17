import argparse
import json

from tradebot.backtest import Backtester, save_backtest_result
from tradebot.config import load_config
from tradebot.data import fetch_binance_klines


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Vini BTC Regime Momentum Bot")
    parser.add_argument("--config", default="backtest.example.yaml", help="Path to backtest YAML config")
    parser.add_argument("--save", action="store_true", help="Save CSV/JSON outputs")
    args = parser.parse_args()

    cfg = load_config(args.config)
    bt = cfg.get("backtest", {})
    symbol = bt.get("symbol", "BTCUSDT")
    interval = bt.get("interval", "1d")
    start = bt.get("start", "2017-08-17")
    end = bt.get("end")

    print(f"Downloading {symbol} {interval} candles from Binance...")
    data = fetch_binance_klines(symbol=symbol, interval=interval, start=start, end=end)
    print(f"Downloaded {len(data)} candles")

    result = Backtester(cfg, data).run()
    print(json.dumps(result.metrics, indent=2, ensure_ascii=False))

    if args.save:
        output_dir = bt.get("output_dir", "backtests/results")
        save_backtest_result(result, output_dir)
        print(f"Saved outputs to {output_dir}")


if __name__ == "__main__":
    main()
