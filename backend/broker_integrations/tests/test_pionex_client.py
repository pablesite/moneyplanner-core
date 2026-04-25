from django.test import SimpleTestCase

from broker_integrations.services.pionex_client import (
    PionexClient,
    PionexTruncatedError,
)


class _FakePionexClient(PionexClient):
    def __init__(self, responses):
        super().__init__(api_key="k", api_secret="s")
        self._responses = responses
        self.calls: list[tuple[str, dict]] = []

    def _signed_get(self, path: str, params: dict | None = None) -> dict:
        effective_params = dict(params or {})
        self.calls.append((path, effective_params))
        key = (path, effective_params.get("endTime"))
        payload = self._responses.get(key)
        if payload is None:
            return {"result": True, "data": {"fills": []}}
        return payload


class PionexClientPaginationTests(SimpleTestCase):
    def test_get_fills_walks_backwards_until_range_is_covered(self):
        # Cursor is now oldest_ms (not oldest_ms-1).
        # The next page uses endTime=oldest_ms so the API may return the boundary
        # record again; _row_key dedup filters it out.
        client = _FakePionexClient(
            responses={
                ("/api/v1/trade/fills", "10000"): {
                    "result": True,
                    "data": {
                        "fills": [
                            {"id": "fill-1", "time": 9000},
                            {"id": "fill-2", "time": 8000},
                        ]
                    },
                },
                ("/api/v1/trade/fills", "8000"): {
                    "result": True,
                    "data": {
                        "fills": [
                            {"id": "fill-2", "time": 8000},  # boundary duplicate — deduped
                            {"id": "fill-3", "time": 7000},
                        ]
                    },
                },
                ("/api/v1/trade/fills", "7000"): {
                    "result": True,
                    "data": {"fills": [{"id": "fill-4", "time": 6500}]},
                },
            }
        )

        rows = client.get_fills(symbol="BTC_USDT", start_ms=1000, end_ms=10000, limit=2)

        self.assertEqual([row["id"] for row in rows], ["fill-1", "fill-2", "fill-3", "fill-4"])
        self.assertEqual(
            [params.get("endTime") for _, params in client.calls],
            ["10000", "8000", "7000"],
        )

    def test_get_dual_records_walks_backwards_until_range_is_covered(self):
        client = _FakePionexClient(
            responses={
                ("/api/v1/earn/dual/records", "10000"): {
                    "result": True,
                    "data": {
                        "records": [
                            {"recordId": "dual-1", "settleTime": 9000},
                            {"recordId": "dual-2", "settleTime": 8500},
                        ]
                    },
                },
                ("/api/v1/earn/dual/records", "8500"): {
                    "result": True,
                    "data": {
                        "records": [
                            {
                                "recordId": "dual-2",
                                "settleTime": 8500,
                            },  # boundary duplicate — deduped
                            {"recordId": "dual-3", "settleTime": 8000},
                        ]
                    },
                },
                ("/api/v1/earn/dual/records", "8000"): {
                    "result": True,
                    "data": {"records": [{"recordId": "dual-4", "settleTime": 7800}]},
                },
            }
        )

        rows = client.get_dual_invest_records(base="BTC", start_ms=1000, end_ms=10000, limit=2)

        self.assertEqual(
            [row["recordId"] for row in rows],
            ["dual-1", "dual-2", "dual-3", "dual-4"],
        )
        self.assertEqual(
            [params.get("endTime") for _, params in client.calls],
            ["10000", "8500", "8000"],
        )

    def test_get_fills_same_timestamp_all_records_does_not_loop(self):
        # If the full batch shares one timestamp the cursor would not advance.
        # The anti-stagnation guard must break rather than loop infinitely.
        same_ts = 5000
        client = _FakePionexClient(
            responses={
                ("/api/v1/trade/fills", "10000"): {
                    "result": True,
                    "data": {
                        "fills": [
                            {"id": "fill-a", "time": same_ts},
                            {"id": "fill-b", "time": same_ts},
                        ]
                    },
                },
                # endTime=same_ts would be an infinite loop without the guard.
                ("/api/v1/trade/fills", str(same_ts)): {
                    "result": True,
                    "data": {
                        "fills": [
                            {"id": "fill-a", "time": same_ts},
                            {"id": "fill-b", "time": same_ts},
                        ]
                    },
                },
            }
        )

        rows = client.get_fills(symbol="BTC_USDT", start_ms=1000, end_ms=10000, limit=2)
        # Guard triggers break; both unique records from first batch are returned.
        self.assertEqual({r["id"] for r in rows}, {"fill-a", "fill-b"})
        # Only 2 API calls: initial + one retry, then guard fires.
        self.assertLessEqual(len(client.calls), 2)

    def test_get_fills_raises_truncated_error_when_max_iterations_reached(self):
        # Every call returns a full batch so the loop never finishes naturally.
        def always_full(path, params=None):
            end = int((params or {}).get("endTime", 0))
            return {
                "result": True,
                "data": {
                    "fills": [
                        {"id": f"fill-{end}-1", "time": max(end - 1, 1)},
                        {"id": f"fill-{end}-2", "time": max(end - 2, 1)},
                    ]
                },
            }

        client = PionexClient.__new__(PionexClient)
        client._signed_get = always_full

        with self.assertRaises(PionexTruncatedError) as ctx:
            client.get_fills(symbol="BTC_USDT", start_ms=1, end_ms=10_000_000, limit=2)

        self.assertGreater(len(ctx.exception.rows), 0)
        self.assertIn("fills:", ctx.exception.source)

    def test_get_bot_spot_grid_orders_raises_truncated_on_timestamp_stagnation(self):
        # Simulate a bot endpoint that always returns the same timestamp.
        stagnant_ts = 7777
        responses = {}
        for st in range(stagnant_ts, stagnant_ts + 500):
            responses[("/api/v1/bot/order/spotGrid/orders", str(stagnant_ts))] = {
                "result": True,
                "data": {
                    "orders": [
                        {"id": f"o-{st}-1", "filledTime": stagnant_ts},
                        {"id": f"o-{st}-2", "filledTime": stagnant_ts},
                    ]
                },
            }

        client = _FakePionexClient(responses=responses)
        client._responses[("/api/v1/bot/order/spotGrid/orders", "99999")] = {
            "result": True,
            "data": {
                "orders": [
                    {"id": "o-init-1", "filledTime": stagnant_ts},
                    {"id": "o-init-2", "filledTime": stagnant_ts},
                ]
            },
        }

        with self.assertRaises(PionexTruncatedError) as ctx:
            client.get_bot_spot_grid_orders("bot-X", start_ms=1000, end_ms=99999, limit=2)

        self.assertIn("bot_fills:", ctx.exception.source)
        self.assertGreater(len(ctx.exception.rows), 0)
