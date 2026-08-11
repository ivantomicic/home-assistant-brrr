"""Pure helpers for Brrr Notifications."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

_WEBHOOK_KEY_PATTERN = re.compile(r"^br_[^\s/]+$")


def normalize_webhook_key(value: str) -> str:
    """Return a Brrr webhook key from either a key or an app webhook URL."""
    candidate = value.strip()
    parsed = urlsplit(candidate)

    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.netloc.lower() != "api.brrr.now":
            raise ValueError("Webhook URL must use https://api.brrr.now")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2 or parts[0] != "v1" or parts[1] == "send":
            raise ValueError("Paste a device or shared webhook URL from the Brrr app")
        candidate = parts[1]

    if not _WEBHOOK_KEY_PATTERN.fullmatch(candidate):
        raise ValueError("Webhook key must start with br_ and contain no spaces")

    return candidate


def webhook_fingerprint(webhook_key: str) -> str:
    """Return a non-secret identifier for a webhook key."""
    digest = hashlib.sha256(webhook_key.encode()).hexdigest()
    return f"webhook_{digest[:20]}"


def parse_retry_after(value: str | None, *, default: float = 0.5) -> float:
    """Parse a non-negative Retry-After delay expressed in seconds."""
    if value is None:
        return default
    try:
        delay = float(value)
    except ValueError:
        return default
    return delay if math.isfinite(delay) and delay >= 0 else default


def build_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Build the Brrr JSON payload, dropping empty optional values."""
    payload: dict[str, Any] = {"message": str(data["message"])}
    optional_fields = (
        "title",
        "subtitle",
        "thread_id",
        "sound",
        "open_url",
        "image_url",
        "icon_url",
        "expiration_date",
        "filter_criteria",
        "interruption_level",
        "volume",
    )

    for field in optional_fields:
        value = data.get(field)
        if value is not None and value != "":
            payload[field] = value

    return payload
