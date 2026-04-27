from unittest.mock import patch

from django.test import SimpleTestCase

from broker_integrations.services.binance_client import BinanceClient


class BinanceClientTests(SimpleTestCase):
    def test_signed_get_uses_server_time_offset_and_recv_window(self):
        client = BinanceClient(api_key="key", api_secret="secret")

        with (
            patch.object(client, "_get_server_time_offset_ms", return_value=5000),
            patch("time.time", return_value=1000.0),
        ):
            with self.assertRaisesRegex(Exception, "stop-before-network"):
                with patch(
                    "urllib.request.urlopen",
                    side_effect=Exception("stop-before-network"),
                ) as mocked_urlopen:
                    client._signed_get("/sapi/v1/test", {"asset": "BTC"})

        request = mocked_urlopen.call_args.args[0]
        self.assertIn("timestamp=1005000", request.full_url)
        self.assertIn("recvWindow=10000", request.full_url)
