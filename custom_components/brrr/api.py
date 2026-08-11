"""Async client for the Brrr webhook API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .const import API_ENDPOINT, API_TIMEOUT_SECONDS


class BrrrError(Exception):
    """Base class for Brrr API failures."""


class BrrrAuthenticationError(BrrrError):
    """Raised when Brrr rejects a webhook key."""


class BrrrConnectionError(BrrrError):
    """Raised when Brrr cannot be reached."""


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
        """Send a notification to Brrr."""
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
                response.raise_for_status()
                return BrrrResponse(status=response.status, body=body)
        except BrrrAuthenticationError:
            raise
        except (ClientError, ClientResponseError, asyncio.TimeoutError) as err:
            raise BrrrConnectionError(f"Unable to send through Brrr: {err}") from err
