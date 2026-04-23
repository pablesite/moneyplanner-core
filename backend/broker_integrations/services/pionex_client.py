from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class PionexApiError(Exception):
    def __init__(self, message: str, *, code: str | None = None, response: dict | None = None):
        super().__init__(message)
        self.code = code
        self.response = response or {}


class PionexClient:
    BASE_URL = "https://api.pionex.com"

    def __init__(self, *, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def _signed_get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        request_params = dict(params or {})
        request_params["timestamp"] = str(int(time.time() * 1000))
        query_string = urllib.parse.urlencode(sorted(request_params.items()))
        payload = f"GET{path}?{query_string}"
        signature = hmac.new(
            self.api_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        request_url = f"{self.BASE_URL}{path}?{query_string}"
        request = urllib.request.Request(
            request_url,
            method="GET",
            headers={
                "PIONEX-KEY": self.api_key,
                "PIONEX-SIGNATURE": signature,
                "User-Agent": "moneyplanner-core/broker-integrations",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload_raw = response.read().decode("utf-8", errors="ignore")
                return json.loads(payload_raw)
        except urllib.error.HTTPError as exc:
            payload_raw = exc.read().decode("utf-8", errors="ignore")
            try:
                error_payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                error_payload = {"message": payload_raw}
            raise PionexApiError(
                f"Pionex HTTP {exc.code}",
                code=str(error_payload.get("code")) if isinstance(error_payload, dict) else None,
                response=error_payload if isinstance(error_payload, dict) else {"raw": payload_raw},
            ) from exc
        except urllib.error.URLError as exc:
            raise PionexApiError(f"Pionex request error: {exc.reason}") from exc

    @staticmethod
    def _extract_data(payload: dict) -> Any:
        if not payload.get("result"):
            raise PionexApiError(
                str(payload.get("message") or "Pionex API error"),
                code=str(payload.get("code")) if payload.get("code") is not None else None,
                response=payload,
            )
        return payload.get("data", {})

    def get_balances(self) -> list[dict]:
        payload = self._signed_get("/api/v1/account/balances")
        data = self._extract_data(payload)
        if isinstance(data, dict):
            balances = data.get("balances")
            if isinstance(balances, list):
                return balances
        if isinstance(data, list):
            return data
        return []

    def get_fills(self, *, symbol: str, start_ms: int, end_ms: int, limit: int = 100) -> list[dict]:
        payload = self._signed_get(
            "/api/v1/trade/fills",
            {
                "symbol": symbol,
                "startTime": str(start_ms),
                "endTime": str(end_ms),
                "limit": str(limit),
            },
        )
        data = self._extract_data(payload)
        if isinstance(data, dict):
            for key in ("fills", "list", "rows", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        if isinstance(data, list):
            return data
        return []

    def get_bot_summary(self, *, bot_id: str) -> dict:
        payload = self._signed_get(
            "/api/v1/bot/orders/spotGrid/order",
            {"botId": bot_id},
        )
        data = self._extract_data(payload)
        return data if isinstance(data, dict) else {}

    def get_bot_orders(
        self,
        *,
        status: str = "running",
        page_token: str | None = None,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None]:
        params: dict[str, str] = {
            "status": status,
            "limit": str(limit),
        }
        if page_token:
            params["pageToken"] = page_token
        payload = self._signed_get("/api/v1/bot/orders", params)
        data = self._extract_data(payload)
        if not isinstance(data, dict):
            return [], None
        rows = data.get("results")
        next_page_token = data.get("nextPageToken")
        if not isinstance(rows, list):
            rows = []
        if not isinstance(next_page_token, str) or not next_page_token.strip():
            next_page_token = None
        return [row for row in rows if isinstance(row, dict)], next_page_token

    def get_dual_invest_records(
        self, *, base: str, start_ms: int, end_ms: int, limit: int = 100
    ) -> list[dict]:
        payload = self._signed_get(
            "/api/v1/earn/dual/records",
            {
                "base": base,
                "startTime": str(start_ms),
                "endTime": str(end_ms),
                "limit": str(limit),
            },
        )
        data = self._extract_data(payload)
        if isinstance(data, dict):
            for key in ("records", "list", "rows", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        if isinstance(data, list):
            return data
        return []
