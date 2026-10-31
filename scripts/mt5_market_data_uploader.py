"""Forward the local MT5 demo quote/candle JSON file to the read-only API."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_RESPONSE_BYTES = 2_048


def _redact_credentials(message: str, secret: str, token: str | None) -> str:
    """Prevent credentials echoed by an endpoint or network error from being printed."""
    for credential in (secret, token):
        if credential:
            message = message.replace(credential, "[REDACTED]")
    return message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload read-only XAUUSDm MT5 DEMO market data over HTTPS."
    )
    parser.add_argument(
        "--file",
        default="mt5_market_data.json",
        help="Path to the Windows bridge's JSON output file.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5,
        help="Seconds between file checks when running continuously (default: 5).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Send the current file once, then exit.",
    )
    return parser


def _load_settings() -> tuple[str, str, str | None]:
    url = os.environ.get("MT5_MARKET_DATA_INGEST_URL", "").strip()
    secret = os.environ.get("MT5_MARKET_DATA_BRIDGE_SECRET", "")
    external_access_token = os.environ.get("REPLIT_EXTERNAL_ACCESS_TOKEN") or None
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username:
        raise ValueError("MT5_MARKET_DATA_INGEST_URL must be a valid HTTPS URL.")
    if len(secret.encode("utf-8")) < 32:
        raise ValueError(
            "MT5_MARKET_DATA_BRIDGE_SECRET must contain at least 32 UTF-8 bytes."
        )
    return url, secret, external_access_token


def _request_body(path: Path) -> bytes:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Market-data file does not exist: {path.resolve()}") from error
    except json.JSONDecodeError as error:
        raise ValueError("Market-data file is not valid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("Market-data file must contain a JSON object.")
    # Serialize once and sign these exact bytes; never include credentials or
    # account fields from the source file in the outbound request.
    allowed = {"symbol", "timestamp", "bid", "ask", "candles"}
    if set(payload) != allowed:
        raise ValueError(
            "JSON must contain only symbol, timestamp, bid, ask, and candles."
        )
    return json.dumps(
        payload, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def upload_once(
    path: Path, url: str, secret: str, external_access_token: str | None = None
) -> bytes:
    body = _request_body(path)
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Bridge-Timestamp": timestamp,
        "X-Bridge-Signature": signature,
        "User-Agent": "xauusd-mt5-readonly-bridge/1",
    }
    if external_access_token:
        headers["Authorization"] = f"Bearer {external_access_token}"
    request = Request(url, data=body, method="POST", headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            response_body = response.read(MAX_RESPONSE_BYTES)
            if response.status != 202:
                raise RuntimeError(f"Bridge API returned HTTP {response.status}.")
            return response_body
    except HTTPError as error:
        response_body = error.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Bridge API returned HTTP {error.code}: {response_body}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the HTTPS bridge API: {error.reason}") from error


def main() -> int:
    args = build_parser().parse_args()
    if args.interval <= 0:
        print("Polling interval must be greater than zero.", file=sys.stderr)
        return 2
    try:
        url, secret, external_access_token = _load_settings()
        file_path = Path(args.file).expanduser()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    last_digest: bytes | None = None
    while True:
        try:
            body = _request_body(file_path)
            digest = hashlib.sha256(body).digest()
            if args.once or digest != last_digest:
                response = upload_once(file_path, url, secret, external_access_token)
                print(
                    _redact_credentials(
                        response.decode("utf-8", errors="replace"),
                        secret,
                        external_access_token,
                    )
                )
                last_digest = digest
            elif args.once:
                break
        except (OSError, ValueError, RuntimeError) as error:
            print(
                _redact_credentials(str(error), secret, external_access_token),
                file=sys.stderr,
            )
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
