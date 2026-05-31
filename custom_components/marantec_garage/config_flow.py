"""Config flow for the Marantec Garage Door integration."""

from __future__ import annotations

from typing import Any

from rf_protocols import ModulationType
from rf_protocols.commands.marantec import MarantecCommand
import voluptuous as vol

from homeassistant.components.radio_frequency import async_get_transmitters
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

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


class MarantecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for a Marantec garage door."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the code, transmitter, and timing options."""
        errors: dict[str, str] = {}

        try:
            transmitters = async_get_transmitters(
                self.hass, _DEFAULT_FREQUENCY, ModulationType.OOK
            )
        except HomeAssistantError:
            transmitters = []

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
                        CONF_AUTO_CLOSE_DELAY: user_input[CONF_AUTO_CLOSE_DELAY],
                        CONF_TRAVEL_UP: user_input[CONF_TRAVEL_UP],
                        CONF_TRAVEL_DOWN: user_input[CONF_TRAVEL_DOWN],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_CODE): str,
                vol.Required(CONF_TRANSMITTER): vol.In(transmitters),
                vol.Required(
                    CONF_AUTO_CLOSE_DELAY, default=DEFAULT_AUTO_CLOSE_DELAY
                ): _NON_NEGATIVE_INT,
                vol.Required(
                    CONF_TRAVEL_UP, default=DEFAULT_TRAVEL_TIME
                ): _NON_NEGATIVE_INT,
                vol.Required(
                    CONF_TRAVEL_DOWN, default=DEFAULT_TRAVEL_TIME
                ): _NON_NEGATIVE_INT,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

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
