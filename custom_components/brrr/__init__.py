"""Brrr Notifications integration."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BrrrAuthenticationError, BrrrClient, BrrrConnectionError
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_EXPIRATION_DATE,
    ATTR_FILTER_CRITERIA,
    ATTR_ICON_MEDIA,
    ATTR_ICON_URL,
    ATTR_IMAGE_MEDIA,
    ATTR_IMAGE_URL,
    ATTR_INTERRUPTION_LEVEL,
    ATTR_MESSAGE,
    ATTR_OPEN_URL,
    ATTR_SOUND,
    ATTR_SUBTITLE,
    ATTR_THREAD_ID,
    ATTR_TITLE,
    ATTR_VOLUME,
    CONF_PUBLIC_MEDIA_ENABLED,
    CONF_PUBLIC_MEDIA_TTL_HOURS,
    CONF_WEBHOOK_KEY,
    DEFAULT_PUBLIC_MEDIA_TTL_HOURS,
    DOMAIN,
    INTERRUPTION_LEVELS,
    SERVICE_SEND_NOTIFICATION,
    SOUNDS,
)
from .helpers import build_payload
from .media import BrrrMediaError, async_resolve_media_image


@dataclass(slots=True)
class BrrrRuntimeData:
    """Runtime data for a configured Brrr target."""

    client: BrrrClient


type BrrrConfigEntry = ConfigEntry[BrrrRuntimeData]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_SUBTITLE): cv.string,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_THREAD_ID): cv.string,
        vol.Optional(ATTR_SOUND): vol.In(SOUNDS),
        vol.Optional(ATTR_OPEN_URL): cv.string,
        vol.Optional(ATTR_IMAGE_URL): cv.string,
        vol.Optional(ATTR_IMAGE_MEDIA): dict,
        vol.Optional(ATTR_ICON_URL): cv.string,
        vol.Optional(ATTR_ICON_MEDIA): dict,
        vol.Optional(ATTR_EXPIRATION_DATE): cv.string,
        vol.Optional(ATTR_FILTER_CRITERIA): cv.string,
        vol.Optional(ATTR_INTERRUPTION_LEVEL): vol.In(INTERRUPTION_LEVELS),
        vol.Optional(ATTR_VOLUME): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up global Brrr actions."""
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_NOTIFICATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_NOTIFICATION,
            partial(_async_send_notification, hass),
            schema=SERVICE_SCHEMA,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BrrrConfigEntry) -> bool:
    """Set up a configured Brrr webhook target."""
    entry.runtime_data = BrrrRuntimeData(
        client=BrrrClient(
            async_get_clientsession(hass),
            entry.data[CONF_WEBHOOK_KEY],
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BrrrConfigEntry) -> bool:
    """Unload a Brrr target."""
    return True


async def _async_send_notification(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the visual Brrr notification action."""
    entry = _select_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    data = dict(call.data)

    if ATTR_ICON_URL in data and ATTR_ICON_MEDIA in data:
        raise ServiceValidationError("Choose either Icon URL or Icon from Media Library")
    if ATTR_IMAGE_URL in data and ATTR_IMAGE_MEDIA in data:
        raise ServiceValidationError("Choose either Image URL or Image from Media Library")

    public_media_enabled = bool(entry.data.get(CONF_PUBLIC_MEDIA_ENABLED, False))
    ttl_hours = int(
        entry.data.get(CONF_PUBLIC_MEDIA_TTL_HOURS, DEFAULT_PUBLIC_MEDIA_TTL_HOURS)
    )

    try:
        if media_selection := data.pop(ATTR_ICON_MEDIA, None):
            data[ATTR_ICON_URL] = await async_resolve_media_image(
                hass,
                media_selection,
                public_media_enabled=public_media_enabled,
                ttl_hours=ttl_hours,
            )
        if media_selection := data.pop(ATTR_IMAGE_MEDIA, None):
            data[ATTR_IMAGE_URL] = await async_resolve_media_image(
                hass,
                media_selection,
                public_media_enabled=public_media_enabled,
                ttl_hours=ttl_hours,
            )
    except BrrrMediaError as err:
        raise ServiceValidationError(str(err)) from err

    _validate_https_asset(data.get(ATTR_ICON_URL), "Icon URL")
    _validate_https_asset(data.get(ATTR_IMAGE_URL), "Image URL")

    payload = build_payload(data)
    try:
        await entry.runtime_data.client.async_send(payload)
    except BrrrAuthenticationError as err:
        raise ServiceValidationError(
            f"Brrr rejected the webhook key for {entry.data.get(CONF_NAME, entry.title)}"
        ) from err
    except BrrrConnectionError as err:
        raise HomeAssistantError(str(err)) from err


def _select_entry(hass: HomeAssistant, entry_id: str | None) -> BrrrConfigEntry:
    """Resolve the selected Brrr webhook target."""
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError("The selected Brrr target no longer exists")
        if entry.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError(f"Brrr target {entry.title} is not loaded")
        return entry

    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not entries:
        raise ServiceValidationError("Configure a Brrr target before sending notifications")
    if len(entries) > 1:
        raise ServiceValidationError("Select a Brrr target when more than one is configured")
    return entries[0]


def _validate_https_asset(value: str | None, label: str) -> None:
    """Require Brrr-hosted notification assets to use HTTPS."""
    if value:
        parsed = urlsplit(value)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ServiceValidationError(f"{label} must be a complete HTTPS URL")
