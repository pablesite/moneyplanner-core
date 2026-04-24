from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any


class BinanceApiError(Exception):
    def __init__(self, message: str, *, code: str | None = None, response: dict | None = None):
        super().__init__(message)
        self.code = code
        self.response = response or {}


class BinanceClient:
    BASE_URL = "https://api.binance.com"

    def __init__(self, *, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def _signed_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_params = {
            key: str(value) for key, value in (params or {}).items() if value is not None
        }
        request_params["timestamp"] = str(int(time.time() * 1000))
        query_string = urllib.parse.urlencode(sorted(request_params.items()))
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        request_url = f"{self.BASE_URL}{path}?{query_string}&signature={signature}"
        request = urllib.request.Request(
            request_url,
            method="GET",
            headers={
                "X-MBX-APIKEY": self.api_key,
                "User-Agent": "moneyplanner-core/broker-integrations",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload_raw = response.read().decode("utf-8", errors="ignore")
                payload = json.loads(payload_raw)
        except urllib.error.HTTPError as exc:
            payload_raw = exc.read().decode("utf-8", errors="ignore")
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                payload = {"msg": payload_raw}
            raise BinanceApiError(
                f"Binance HTTP {exc.code}",
                code=str(payload.get("code")) if isinstance(payload, dict) else None,
                response=payload if isinstance(payload, dict) else {"raw": payload_raw},
            ) from exc
        except urllib.error.URLError as exc:
            raise BinanceApiError(f"Binance request error: {exc.reason}") from exc

        if isinstance(payload, dict) and payload.get("code") not in (None, 200, "200"):
            raise BinanceApiError(
                str(payload.get("msg") or "Binance API error"),
                code=str(payload.get("code")),
                response=payload,
            )
        return payload if isinstance(payload, dict) else {"data": payload}

    @staticmethod
    def _extract_rows(payload: dict[str, Any], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        if isinstance(payload.get("data"), list):
            return [row for row in payload["data"] if isinstance(row, dict)]
        return []

    @staticmethod
    def _iter_date_windows(
        *, start_ms: int, end_ms: int, window_days: int
    ) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        current = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
        while current <= end_dt:
            window_end = min(
                current + timedelta(days=window_days) - timedelta(milliseconds=1), end_dt
            )
            windows.append((int(current.timestamp() * 1000), int(window_end.timestamp() * 1000)))
            current = window_end + timedelta(milliseconds=1)
        return windows

    def get_convert_history(self, *, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for window_start, window_end in self._iter_date_windows(
            start_ms=start_ms, end_ms=end_ms, window_days=30
        ):
            payload = self._signed_get(
                "/sapi/v1/convert/tradeFlow",
                {
                    "startTime": window_start,
                    "endTime": window_end,
                    "limit": 1000,
                },
            )
            rows.extend(self._extract_rows(payload, keys=("list", "rows", "data", "items")))
        return rows

    def get_earn_flexible_rewards(
        self,
        *,
        asset: str,
        start_ms: int,
        end_ms: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for window_start, window_end in self._iter_date_windows(
            start_ms=start_ms, end_ms=end_ms, window_days=90
        ):
            page = 1
            while True:
                payload = self._signed_get(
                    "/sapi/v1/simple-earn/flexible/history/rewardsRecord",
                    {
                        "asset": asset,
                        "type": "ALL",
                        "startTime": window_start,
                        "endTime": window_end,
                        "current": page,
                        "size": 100,
                    },
                )
                page_rows = self._extract_rows(payload, keys=("rows", "list", "data", "items"))
                rows.extend(page_rows)
                if len(page_rows) < 100:
                    break
                page += 1
                if page > 200:
                    break
        return rows

    def get_pay_transactions(self, *, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for window_start, window_end in self._iter_date_windows(
            start_ms=start_ms, end_ms=end_ms, window_days=90
        ):
            page = 1
            while True:
                payload = self._signed_get(
                    "/sapi/v1/pay/transactions",
                    {
                        "startTimestamp": window_start,
                        "endTimestamp": window_end,
                        "limit": 100,
                        "page": page,
                    },
                )
                page_rows = self._extract_rows(payload, keys=("data", "rows", "list", "items"))
                rows.extend(page_rows)
                if len(page_rows) < 100:
                    break
                page += 1
                if page > 200:
                    break
        return rows

    def get_referral_rebates(self, *, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for window_start, window_end in self._iter_date_windows(
            start_ms=start_ms, end_ms=end_ms, window_days=30
        ):
            payload = self._signed_get(
                "/sapi/v1/rebate/taxQuery",
                {
                    "startTime": window_start,
                    "endTime": window_end,
                    "page": 1,
                    "size": 500,
                },
            )
            rows.extend(self._extract_rows(payload, keys=("data", "rows", "list", "items")))
        return rows
