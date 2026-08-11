"""Brrr Notifications integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api import (
    BrrrAuthenticationError,
    BrrrClient,
    BrrrConnectionError,
    BrrrRateLimitError,
    BrrrRequestError,
    BrrrServerError,
    BrrrTimeoutError,
)
from .const import (
    API_TIMEOUT_SECONDS,
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
    MEDIA_CLEANUP_INTERVAL_HOURS,
    SERVICE_CLEANUP_MEDIA,
    SERVICE_SEND_NOTIFICATION,
    SOUNDS,
)
from .helpers import build_payload
from .media import (
    BrrrMediaError,
    async_cleanup_media_cache,
    async_resolve_media_image,
)

PLATFORMS = [Platform.BUTTON]

_DATA_CLEANUP_UNSUB = "cleanup_unsub"
_DATA_LOADED_ENTRIES = "loaded_entries"


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
    hass.data.setdefault(
        DOMAIN,
        {
            _DATA_LOADED_ENTRIES: set(),
        },
    )
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_NOTIFICATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_NOTIFICATION,
            partial(_async_send_notification, hass),
            schema=SERVICE_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CLEANUP_MEDIA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEANUP_MEDIA,
            partial(_async_cleanup_media, hass),
            schema=vol.Schema({}),
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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    domain_data = hass.data[DOMAIN]
    loaded_entries: set[str] = domain_data[_DATA_LOADED_ENTRIES]
    loaded_entries.add(entry.entry_id)

    await async_cleanup_media_cache(hass, _minimum_media_ttl_hours(hass))
    if _DATA_CLEANUP_UNSUB not in domain_data:
        domain_data[_DATA_CLEANUP_UNSUB] = async_track_time_interval(
            hass,
            partial(_async_scheduled_media_cleanup, hass),
            timedelta(hours=MEDIA_CLEANUP_INTERVAL_HOURS),
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BrrrConfigEntry) -> bool:
    """Unload a Brrr target."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    domain_data = hass.data[DOMAIN]
    loaded_entries: set[str] = domain_data[_DATA_LOADED_ENTRIES]
    loaded_entries.discard(entry.entry_id)
    if not loaded_entries:
        cleanup_unsub: Callable[[], None] | None = domain_data.pop(
            _DATA_CLEANUP_UNSUB,
            None,
        )
        if cleanup_unsub is not None:
            cleanup_unsub()
    return True


async def async_send_payload(
    hass: HomeAssistant,
    entry: BrrrConfigEntry,
    payload: dict[str, Any],
) -> None:
    """Send a payload and translate Brrr failures into Home Assistant errors."""
    try:
        await entry.runtime_data.client.async_send(payload)
    except BrrrAuthenticationError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
            translation_placeholders={
                "target": entry.data.get(CONF_NAME, entry.title),
            },
        ) from err
    except BrrrRateLimitError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="rate_limited",
            translation_placeholders={
                "retry_after": f"{err.retry_after:g}",
            },
        ) from err
    except BrrrServerError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="server_error",
            translation_placeholders={"status": str(err.status)},
        ) from err
    except BrrrTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout",
            translation_placeholders={"timeout": str(API_TIMEOUT_SECONDS)},
        ) from err
    except BrrrRequestError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="request_rejected",
            translation_placeholders={"status": str(err.status)},
        ) from err
    except BrrrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={"reason": str(err)},
        ) from err


async def _async_send_notification(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the visual Brrr notification action."""
    entry = _select_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    data = dict(call.data)

    if ATTR_ICON_URL in data and ATTR_ICON_MEDIA in data:
        raise ServiceValidationError(
            "Choose either Icon URL or Icon from Media Library"
        )
    if ATTR_IMAGE_URL in data and ATTR_IMAGE_MEDIA in data:
        raise ServiceValidationError(
            "Choose either Image URL or Image from Media Library"
        )

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

    await async_send_payload(hass, entry, build_payload(data))


async def _async_cleanup_media(hass: HomeAssistant, call: ServiceCall) -> None:
    """Remove all generated public-media files on demand."""
    await async_cleanup_media_cache(
        hass,
        _minimum_media_ttl_hours(hass),
        remove_all=True,
    )


async def _async_scheduled_media_cleanup(
    hass: HomeAssistant,
    now: datetime,
) -> None:
    """Remove expired generated public-media files."""
    await async_cleanup_media_cache(hass, _minimum_media_ttl_hours(hass))


def _minimum_media_ttl_hours(hass: HomeAssistant) -> int:
    """Use the shortest configured retention across public-media targets."""
    values = [
        int(entry.data.get(CONF_PUBLIC_MEDIA_TTL_HOURS, DEFAULT_PUBLIC_MEDIA_TTL_HOURS))
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_PUBLIC_MEDIA_ENABLED, False)
    ]
    return min(values, default=DEFAULT_PUBLIC_MEDIA_TTL_HOURS)


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
        raise ServiceValidationError(
            "Configure a Brrr target before sending notifications"
        )
    if len(entries) > 1:
        raise ServiceValidationError(
            "Select a Brrr target when more than one is configured"
        )
    return entries[0]


def _validate_https_asset(value: str | None, label: str) -> None:
    """Require Brrr-hosted notification assets to use HTTPS."""
    if value:
        parsed = urlsplit(value)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ServiceValidationError(f"{label} must be a complete HTTPS URL")
