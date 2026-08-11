"""Diagnostics for Brrr Notifications."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import BrrrConfigEntry
from .const import CONF_WEBHOOK_KEY


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BrrrConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without exposing the webhook secret."""
    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "data": {
            key: "**REDACTED**" if key == CONF_WEBHOOK_KEY else value
            for key, value in entry.data.items()
        },
    }
