"""Config flow for the Marantec Garage Door integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.radio_frequency import async_get_transmitters
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from rf_protocols import ModulationType
from rf_protocols.commands.marantec import MarantecCommand

from . import MarantecConfigEntry
from .const import (
    CONF_AUTO_CLOSE_DELAY,
    CONF_CODE,
    CONF_TRANSMITTER,
    CONF_TRAVEL_DOWN,
    CONF_TRAVEL_UP,
    DEFAULT_AUTO_CLOSE_DELAY,
    DEFAULT_TRAVEL_TIME,
    DOMAIN,
)

# Frequency/modulation used to filter compatible transmitters. Mirrors the
# defaults of MarantecCommand so the picker only offers usable transmitters.
_DEFAULT_FREQUENCY = MarantecCommand(code=0).frequency

_NON_NEGATIVE_INT = vol.All(vol.Coerce(int), vol.Range(min=0))


def _parse_code(raw: str) -> int:
    """Parse a user-supplied Marantec code (hex, with or without 0x)."""
    text = raw.strip().lower().removeprefix("0x").replace(" ", "")
    value = int(text, 16)
    # Validated against the 49-bit range by constructing the command.
    MarantecCommand(code=value)
    return value


def _options_schema(
    auto_close_delay: int, travel_up: int, travel_down: int
) -> vol.Schema:
    """Build the schema for the adjustable timing options."""
    return vol.Schema(
        {
            vol.Required(
                CONF_AUTO_CLOSE_DELAY, default=auto_close_delay
            ): _NON_NEGATIVE_INT,
            vol.Required(CONF_TRAVEL_UP, default=travel_up): _NON_NEGATIVE_INT,
            vol.Required(CONF_TRAVEL_DOWN, default=travel_down): _NON_NEGATIVE_INT,
        }
    )


def _device_schema(
    transmitters: list[str], code: str = "", transmitter: str | None = None
) -> vol.Schema:
    """Build the schema for the code and transmitter (used by setup + reconfigure)."""
    return vol.Schema(
        {
            vol.Required(CONF_CODE, default=code): str,
            vol.Required(
                CONF_TRANSMITTER,
                default=transmitter if transmitter in transmitters else vol.UNDEFINED,
            ): vol.In(transmitters),
        }
    )


def _available_transmitters(hass: Any) -> list[str]:
    """Return compatible RF transmitters, or an empty list if none exist."""
    try:
        return async_get_transmitters(hass, _DEFAULT_FREQUENCY, ModulationType.OOK)
    except HomeAssistantError:
        return []


class MarantecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for a Marantec garage door."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the code, transmitter, and initial timing options."""
        errors: dict[str, str] = {}

        transmitters = _available_transmitters(self.hass)
        if not transmitters:
            return self.async_abort(reason="no_transmitters")

        if user_input is not None:
            try:
                code = _parse_code(user_input[CONF_CODE])
            except ValueError:
                errors[CONF_CODE] = "invalid_code"
            else:
                await self.async_set_unique_id(str(code))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Marantec {code:013X}",
                    data={
                        CONF_CODE: code,
                        CONF_TRANSMITTER: user_input[CONF_TRANSMITTER],
                    },
                    options={
                        CONF_AUTO_CLOSE_DELAY: DEFAULT_AUTO_CLOSE_DELAY,
                        CONF_TRAVEL_UP: DEFAULT_TRAVEL_TIME,
                        CONF_TRAVEL_DOWN: DEFAULT_TRAVEL_TIME,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_device_schema(
                transmitters,
                code=user_input[CONF_CODE] if user_input else "",
                transmitter=user_input[CONF_TRANSMITTER] if user_input else None,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the code and transmitter of an existing entry.

        The entry (and its entity unique_id) is preserved, so history and
        automations survive a code change.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        transmitters = _available_transmitters(self.hass)
        if not transmitters:
            return self.async_abort(reason="no_transmitters")

        if user_input is not None:
            try:
                code = _parse_code(user_input[CONF_CODE])
            except ValueError:
                errors[CONF_CODE] = "invalid_code"
            else:
                # Allow keeping this entry's own code; block colliding with a
                # different existing entry.
                await self.async_set_unique_id(str(code))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    title=f"Marantec {code:013X}",
                    data={
                        CONF_CODE: code,
                        CONF_TRANSMITTER: user_input[CONF_TRANSMITTER],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_device_schema(
                transmitters,
                code=format(entry.data[CONF_CODE], "013X"),
                transmitter=entry.data[CONF_TRANSMITTER],
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: MarantecConfigEntry,
    ) -> MarantecOptionsFlow:
        """Return the options flow handler."""
        return MarantecOptionsFlow()


class MarantecOptionsFlow(OptionsFlow):
    """Allow adjusting the timing options after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the auto-close delay and travel times."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = _options_schema(
            options.get(CONF_AUTO_CLOSE_DELAY, DEFAULT_AUTO_CLOSE_DELAY),
            options.get(CONF_TRAVEL_UP, DEFAULT_TRAVEL_TIME),
            options.get(CONF_TRAVEL_DOWN, DEFAULT_TRAVEL_TIME),
        )
        return self.async_show_form(step_id="init", data_schema=schema)
