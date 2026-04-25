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


class PionexTruncatedError(Exception):
    """Raised when max_iterations is exhausted before the full range is covered."""

    def __init__(self, rows: list[dict], *, source: str) -> None:
        super().__init__(f"max_iterations reached for {source}; data may be incomplete")
        self.rows = rows
        self.source = source


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

    @staticmethod
    def _extract_rows(data: Any, *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
        if isinstance(data, dict):
            for key in keys:
                rows = data.get(key)
                if isinstance(rows, list):
                    return [row for row in rows if isinstance(row, dict)]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return []

    @staticmethod
    def _row_timestamp_ms(row: dict[str, Any], *, keys: tuple[str, ...]) -> int | None:
        for key in keys:
            value = row.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text.isdigit():
                return int(text)
        return None

    @staticmethod
    def _row_key(row: dict[str, Any]) -> str | None:
        for key in ("id", "tradeId", "orderId", "filledId", "incomeId", "recordId"):
            value = row.get(key)
            if value in (None, ""):
                continue
            return f"{key}:{value}"
        return None

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
        # Endpoint returns the latest N rows in a range; walk backwards by endTime.
        rows: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        cursor_end_ms = end_ms
        max_iterations = 500

        for _ in range(max_iterations):
            payload = self._signed_get(
                "/api/v1/trade/fills",
                {
                    "symbol": symbol,
                    "startTime": str(start_ms),
                    "endTime": str(cursor_end_ms),
                    "limit": str(limit),
                },
            )
            data = self._extract_data(payload)
            batch = self._extract_rows(data, keys=("fills", "list", "rows", "items"))
            if not batch:
                break

            for row in batch:
                row_key = self._row_key(row)
                if row_key and row_key in seen_keys:
                    continue
                if row_key:
                    seen_keys.add(row_key)
                rows.append(row)

            if len(batch) < limit:
                break

            oldest_ms: int | None = None
            for row in batch:
                timestamp_ms = self._row_timestamp_ms(
                    row,
                    keys=("time", "timestamp", "createTime", "filledTime", "updateTime"),
                )
                if timestamp_ms is None:
                    continue
                oldest_ms = timestamp_ms if oldest_ms is None else min(oldest_ms, timestamp_ms)

            if oldest_ms is None or oldest_ms <= start_ms:
                break
            # Use oldest_ms (not oldest_ms-1) so records sharing that exact timestamp
            # are included in the next page; _row_key dedup prevents duplicates.
            if oldest_ms == cursor_end_ms:
                # Cursor did not advance: all records share the same timestamp.
                # Dedup already handles any overlap; stop to avoid infinite loop.
                break
            cursor_end_ms = oldest_ms
        else:
            # for-loop exhausted max_iterations without a break => range not fully covered.
            raise PionexTruncatedError(rows, source=f"fills:{symbol}")

        return rows

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

    def get_bot_spot_grid_orders(
        self,
        bot_id: str,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        rows: list[dict] = []
        path = "/api/v1/bot/order/spotGrid/orders"
        page_token: str | None = None
        current_start_ms = start_ms
        prev_last_timestamp: int | None = None
        max_iterations = 200

        for _ in range(max_iterations):
            params: dict[str, str] = {"botId": str(bot_id), "limit": str(limit)}
            if current_start_ms is not None:
                params["startTime"] = str(current_start_ms)
            if end_ms is not None:
                params["endTime"] = str(end_ms)
            if page_token:
                params["pageToken"] = page_token

            payload = self._signed_get(path, params)
            data = self._extract_data(payload)
            if not isinstance(data, dict):
                break

            batch: list[dict[str, Any]] = []
            for key in ("orders", "results", "list", "rows", "items"):
                candidate = data.get(key)
                if isinstance(candidate, list):
                    batch = [item for item in candidate if isinstance(item, dict)]
                    break

            rows.extend(batch)

            next_page_token = data.get("nextPageToken")
            if isinstance(next_page_token, str) and next_page_token.strip():
                page_token = next_page_token
                continue

            if start_ms is not None and end_ms is not None and len(batch) >= limit:
                last_timestamp: int | None = None
                for row in reversed(batch):
                    for key in ("filledTime", "timestamp", "time", "createTime", "updateTime"):
                        raw = row.get(key)
                        if raw is None:
                            continue
                        text = str(raw).strip()
                        if text.isdigit():
                            last_timestamp = int(text)
                            break
                    if last_timestamp is not None:
                        break
                if last_timestamp is None or last_timestamp >= end_ms:
                    break
                # Detect stagnation: timestamp did not advance between pages.
                if last_timestamp == prev_last_timestamp:
                    raise PionexTruncatedError(rows, source=f"bot_fills:{bot_id}")
                prev_last_timestamp = last_timestamp
                current_start_ms = last_timestamp + 1
                page_token = None
                continue
            break
        else:
            raise PionexTruncatedError(rows, source=f"bot_fills:{bot_id}")

        return rows

    def get_dual_invest_records(
        self, *, base: str, start_ms: int, end_ms: int, limit: int = 100
    ) -> list[dict]:
        rows: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        cursor_end_ms = end_ms
        max_iterations = 500

        for _ in range(max_iterations):
            payload = self._signed_get(
                "/api/v1/earn/dual/records",
                {
                    "base": base,
                    "startTime": str(start_ms),
                    "endTime": str(cursor_end_ms),
                    "limit": str(limit),
                },
            )
            data = self._extract_data(payload)
            batch = self._extract_rows(data, keys=("records", "list", "rows", "items"))
            if not batch:
                break

            for row in batch:
                row_key = self._row_key(row)
                if row_key and row_key in seen_keys:
                    continue
                if row_key:
                    seen_keys.add(row_key)
                rows.append(row)

            if len(batch) < limit:
                break

            oldest_ms: int | None = None
            for row in batch:
                timestamp_ms = self._row_timestamp_ms(
                    row,
                    keys=("settleTime", "time", "timestamp", "createTime", "updateTime"),
                )
                if timestamp_ms is None:
                    continue
                oldest_ms = timestamp_ms if oldest_ms is None else min(oldest_ms, timestamp_ms)

            if oldest_ms is None or oldest_ms <= start_ms:
                break
            if oldest_ms == cursor_end_ms:
                break
            cursor_end_ms = oldest_ms
        else:
            raise PionexTruncatedError(rows, source=f"dual_records:{base}")

        return rows
