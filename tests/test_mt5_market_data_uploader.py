import contextlib
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from scripts import mt5_market_data_uploader as uploader


class _Response:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return b'{"accepted":true}'


class UploaderAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.secret = "s" * 32
        self.token = "development-token-do-not-print"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.payload_path = Path(self.temp_dir.name) / "market.json"
        self.payload_path.write_text(
            json.dumps(
                {
                    "symbol": "XAUUSDm",
                    "timestamp": "2026-10-29T12:00:00Z",
                    "bid": 1,
                    "ask": 2,
                    "candles": [],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _upload_and_headers(self, token=None):
        request_seen = {}

        def fake_urlopen(request, timeout):
            request_seen["request"] = request
            request_seen["timeout"] = timeout
            return _Response()

        with patch.object(uploader, "urlopen", fake_urlopen):
            uploader.upload_once(
                self.payload_path,
                "https://example.test/api/market-data/mt5-demo",
                self.secret,
                token,
            )
        return request_seen["request"].headers

    def test_token_adds_bearer_authorization_and_keeps_hmac_headers(self):
        headers = self._upload_and_headers(self.token)
        self.assertEqual(headers["Authorization"], f"Bearer {self.token}")
        self.assertIn("X-bridge-timestamp", headers)
        self.assertIn("X-bridge-signature", headers)
        self.assertNotIn(self.secret, repr(headers))

    def test_unset_token_preserves_hmac_only_behavior(self):
        headers = self._upload_and_headers()
        self.assertNotIn("Authorization", headers)
        self.assertIn("X-bridge-timestamp", headers)
        self.assertIn("X-bridge-signature", headers)

    def test_hmac_signature_covers_timestamp_and_exact_request_body(self):
        request_seen = {}

        def fake_urlopen(request, timeout):
            request_seen["request"] = request
            return _Response()

        with (
            patch.object(uploader, "urlopen", fake_urlopen),
            patch.object(uploader.time, "time", return_value=1_761_734_400),
        ):
            uploader.upload_once(
                self.payload_path,
                "https://example.test/api/market-data/mt5-demo",
                self.secret,
            )

        request = request_seen["request"]
        timestamp = request.headers["X-bridge-timestamp"]
        expected_signature = hmac.new(
            self.secret.encode("utf-8"),
            timestamp.encode("ascii") + b"." + request.data,
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(request.headers["X-bridge-signature"], expected_signature)

    def test_optional_token_is_loaded_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "MT5_MARKET_DATA_INGEST_URL": "https://example.test/ingest",
                "MT5_MARKET_DATA_BRIDGE_SECRET": self.secret,
                "REPLIT_EXTERNAL_ACCESS_TOKEN": self.token,
            },
            clear=True,
        ):
            _url, _secret, token = uploader._load_settings()
        self.assertEqual(token, self.token)

    def test_credentials_are_redacted_from_printable_text(self):
        message = f"server echoed {self.secret} and {self.token}"
        safe = uploader._redact_credentials(message, self.secret, self.token)
        self.assertNotIn(self.secret, safe)
        self.assertNotIn(self.token, safe)

    def test_cli_redacts_credentials_echoed_in_http_error_output(self):
        error_body = f"server echoed {self.secret} and {self.token}".encode("utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()

        def fake_urlopen(request, timeout):
            raise HTTPError(
                request.full_url,
                403,
                "Forbidden",
                hdrs=None,
                fp=io.BytesIO(error_body),
            )

        with (
            patch.object(uploader, "urlopen", fake_urlopen),
            patch.dict(
                os.environ,
                {
                    "MT5_MARKET_DATA_INGEST_URL": "https://example.test/ingest",
                    "MT5_MARKET_DATA_BRIDGE_SECRET": self.secret,
                    "REPLIT_EXTERNAL_ACCESS_TOKEN": self.token,
                },
                clear=True,
            ),
            patch(
                "sys.argv",
                [
                    "mt5_market_data_uploader.py",
                    "--file",
                    str(self.payload_path),
                    "--once",
                ],
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = uploader.main()

        output = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(result, 1)
        self.assertNotIn(self.secret, output)
        self.assertNotIn(self.token, output)
        self.assertIn("[REDACTED]", output)


if __name__ == "__main__":
    unittest.main()
