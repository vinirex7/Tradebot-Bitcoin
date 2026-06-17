import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

import pandas as pd
import requests


class BinanceClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("BINANCE_BASE_URL") or "https://api.binance.com").rstrip("/")
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def _request(self, method: str, path: str, params: dict | None = None, signed: bool = False) -> dict | list:
        params = params or {}
        if signed:
            if not self.api_key or not self.api_secret:
                raise RuntimeError("Missing BINANCE_API_KEY or BINANCE_API_SECRET")
            params["timestamp"] = int(time.time() * 1000)
            query = urlencode(params, doseq=True)
            signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            params["signature"] = signature
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def exchange_info(self, symbol: str) -> dict:
        return self._request("GET", "/api/v3/exchangeInfo", {"symbol": symbol})

    def klines(self, symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
        raw = self._request("GET", "/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        cols = [
            "open_time", "open", "high", "low", "close", "volume", "close_time",
            "quote_volume", "trades", "taker_base", "taker_quote", "ignore"
        ]
        df = pd.DataFrame(raw, columns=cols)
        for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_base", "taker_quote"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        return df

    def account(self) -> dict:
        return self._request("GET", "/api/v3/account", {"recvWindow": 5000}, signed=True)

    def open_orders(self, symbol: str) -> list[dict]:
        return self._request("GET", "/api/v3/openOrders", {"symbol": symbol, "recvWindow": 5000}, signed=True)

    def market_buy_quote(self, symbol: str, quote_order_qty: float) -> dict:
        return self._request("POST", "/api/v3/order", {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": f"{quote_order_qty:.2f}",
            "recvWindow": 5000,
        }, signed=True)

    def market_sell_qty(self, symbol: str, quantity: float) -> dict:
        return self._request("POST", "/api/v3/order", {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": f"{quantity:.8f}",
            "recvWindow": 5000,
        }, signed=True)
