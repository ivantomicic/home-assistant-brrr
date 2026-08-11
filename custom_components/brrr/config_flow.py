"""Config flow for Brrr Notifications."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_PUBLIC_MEDIA_ENABLED,
    CONF_PUBLIC_MEDIA_TTL_HOURS,
    CONF_WEBHOOK_KEY,
    DEFAULT_NAME,
    DEFAULT_PUBLIC_MEDIA_TTL_HOURS,
    DOMAIN,
)
from .helpers import normalize_webhook_key, webhook_fingerprint


def _schema(
    defaults: dict[str, Any] | None = None, *, key_required: bool = True
) -> vol.Schema:
    """Build the setup/reconfigure form schema."""
    defaults = defaults or {}
    key_marker: vol.Marker
    if key_required:
        key_marker = vol.Required(CONF_WEBHOOK_KEY)
    else:
        key_marker = vol.Optional(CONF_WEBHOOK_KEY)

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
            ): TextSelector(),
            key_marker: TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD,
                    autocomplete="off",
                )
            ),
            vol.Optional(
                CONF_PUBLIC_MEDIA_ENABLED,
                default=defaults.get(CONF_PUBLIC_MEDIA_ENABLED, False),
            ): BooleanSelector(),
            vol.Optional(
                CONF_PUBLIC_MEDIA_TTL_HOURS,
                default=defaults.get(
                    CONF_PUBLIC_MEDIA_TTL_HOURS,
                    DEFAULT_PUBLIC_MEDIA_TTL_HOURS,
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=336,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


class BrrrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Brrr configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up Brrr from the integrations UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                webhook_key = normalize_webhook_key(user_input[CONF_WEBHOOK_KEY])
            except ValueError:
                errors[CONF_WEBHOOK_KEY] = "invalid_webhook"
            else:
                await self.async_set_unique_id(webhook_fingerprint(webhook_key))
                self._abort_if_unique_id_configured()
                data = {**user_input, CONF_WEBHOOK_KEY: webhook_key}
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update a Brrr target and rotated webhook key."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_key = user_input.get(CONF_WEBHOOK_KEY)
            if raw_key:
                try:
                    webhook_key = normalize_webhook_key(raw_key)
                except ValueError:
                    errors[CONF_WEBHOOK_KEY] = "invalid_webhook"
                else:
                    user_input[CONF_WEBHOOK_KEY] = webhook_key
            else:
                user_input[CONF_WEBHOOK_KEY] = entry.data[CONF_WEBHOOK_KEY]

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    title=user_input[CONF_NAME],
                    data_updates=user_input,
                )

        defaults = dict(entry.data)
        defaults.pop(CONF_WEBHOOK_KEY, None)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(defaults, key_required=False),
            errors=errors,
        )
