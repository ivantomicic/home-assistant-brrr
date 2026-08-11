"""Async client for the Brrr webhook API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    API_ENDPOINT,
    API_MAX_ATTEMPTS,
    API_MAX_RETRY_DELAY_SECONDS,
    API_TIMEOUT_SECONDS,
)
from .helpers import parse_retry_after


class BrrrError(Exception):
    """Base class for Brrr API failures."""


class BrrrAuthenticationError(BrrrError):
    """Raised when Brrr rejects a webhook key."""


class BrrrConnectionError(BrrrError):
    """Raised when Brrr cannot be reached."""


class BrrrRequestError(BrrrError):
    """Raised when Brrr rejects a notification payload."""

    def __init__(self, status: int) -> None:
        super().__init__(f"Brrr rejected the notification (HTTP {status})")
        self.status = status


class BrrrRateLimitError(BrrrError):
    """Raised when Brrr continues to rate limit after a bounded retry."""

    def __init__(self, retry_after: float) -> None:
        super().__init__("Brrr is rate limiting notifications")
        self.retry_after = retry_after


class BrrrServerError(BrrrError):
    """Raised when Brrr continues to fail after a bounded retry."""

    def __init__(self, status: int) -> None:
        super().__init__(f"Brrr returned a server error ({status})")
        self.status = status


class BrrrTimeoutError(BrrrError):
    """Raised when Brrr does not respond before the timeout."""


@dataclass(slots=True)
class BrrrResponse:
    """Result of a Brrr notification request."""

    status: int
    body: str


class BrrrClient:
    """Small client for sending Brrr notifications."""

    def __init__(self, session: ClientSession, webhook_key: str) -> None:
        """Initialize the client."""
        self._session = session
        self._webhook_key = webhook_key

    async def async_send(self, payload: dict[str, Any]) -> BrrrResponse:
        """Send a notification with bounded retries for explicit transient responses."""
        for attempt in range(API_MAX_ATTEMPTS):
            try:
                async with self._session.post(
                    API_ENDPOINT,
                    headers={"Authorization": f"Bearer {self._webhook_key}"},
                    json=payload,
                    timeout=ClientTimeout(total=API_TIMEOUT_SECONDS),
                ) as response:
                    body = await response.text()
                    if response.status in (401, 403):
                        raise BrrrAuthenticationError("Brrr rejected the webhook key")

                    if response.status == 429:
                        retry_after = parse_retry_after(
                            response.headers.get("Retry-After")
                        )
                        if attempt + 1 < API_MAX_ATTEMPTS:
                            await asyncio.sleep(
                                min(retry_after, API_MAX_RETRY_DELAY_SECONDS)
                            )
                            continue
                        raise BrrrRateLimitError(retry_after)

                    if response.status >= 500:
                        if attempt + 1 < API_MAX_ATTEMPTS:
                            await asyncio.sleep(
                                min(0.5 * (2**attempt), API_MAX_RETRY_DELAY_SECONDS)
                            )
                            continue
                        raise BrrrServerError(response.status)

                    if response.status >= 400:
                        raise BrrrRequestError(response.status)

                    return BrrrResponse(status=response.status, body=body)
            except BrrrError:
                raise
            except asyncio.TimeoutError as err:
                raise BrrrTimeoutError("Brrr request timed out") from err
            except ClientError as err:
                raise BrrrConnectionError(str(err)) from err

        raise RuntimeError("Brrr retry loop exited unexpectedly")
