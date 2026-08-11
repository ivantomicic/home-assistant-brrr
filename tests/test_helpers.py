"""Tests for pure Brrr helpers."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_helpers():
    path = Path(__file__).parents[1] / "custom_components" / "brrr" / "helpers.py"
    spec = importlib.util.spec_from_file_location("brrr_helpers", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helpers = _load_helpers()


class NormalizeWebhookKeyTests(unittest.TestCase):
    """Test webhook key normalization."""

    def test_accepts_key(self) -> None:
        self.assertEqual(
            helpers.normalize_webhook_key(" br_usr_abc12345 "),
            "br_usr_abc12345",
        )

    def test_extracts_key_from_url(self) -> None:
        self.assertEqual(
            helpers.normalize_webhook_key("https://api.brrr.now/v1/br_dev_abc12345"),
            "br_dev_abc12345",
        )

    def test_rejects_send_endpoint(self) -> None:
        with self.assertRaises(ValueError):
            helpers.normalize_webhook_key("https://api.brrr.now/v1/send")

    def test_rejects_other_hosts(self) -> None:
        with self.assertRaises(ValueError):
            helpers.normalize_webhook_key("https://example.com/v1/br_usr_abc12345")


class PayloadTests(unittest.TestCase):
    """Test Brrr payload generation."""

    def test_drops_empty_optional_values(self) -> None:
        self.assertEqual(
            helpers.build_payload(
                {
                    "message": "Hello",
                    "title": "Home Assistant",
                    "thread_id": "",
                    "icon_url": None,
                    "volume": 0,
                }
            ),
            {"message": "Hello", "title": "Home Assistant", "volume": 0},
        )


class RetryAfterTests(unittest.TestCase):
    """Test Retry-After parsing for bounded API retries."""

    def test_parses_seconds(self) -> None:
        self.assertEqual(helpers.parse_retry_after("1.5"), 1.5)

    def test_uses_default_for_invalid_or_negative_values(self) -> None:
        self.assertEqual(helpers.parse_retry_after(None), 0.5)
        self.assertEqual(helpers.parse_retry_after("tomorrow"), 0.5)
        self.assertEqual(helpers.parse_retry_after("-1"), 0.5)
        self.assertEqual(helpers.parse_retry_after("inf"), 0.5)


if __name__ == "__main__":
    unittest.main()
