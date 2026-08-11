"""Button entities for Brrr Notifications."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BrrrConfigEntry, async_send_payload
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrrrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Brrr button entities."""
    async_add_entities([BrrrTestNotificationButton(entry)])


class BrrrTestNotificationButton(ButtonEntity):
    """Send a real test notification to one Brrr target."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "test_notification"

    def __init__(self, entry: BrrrConfigEntry) -> None:
        """Initialize the test button."""
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_test_notification"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Brrr",
            model="Notification target",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://brrr.now/",
        )

    async def async_press(self) -> None:
        """Send the test notification."""
        await async_send_payload(
            self.hass,
            self._entry,
            {
                "title": "Brrr test",
                "message": (
                    "Home Assistant can send notifications to "
                    f"{self._entry.title}."
                ),
                "thread_id": "home-assistant-brrr-test",
            },
        )
