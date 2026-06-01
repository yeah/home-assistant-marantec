"""Cover platform for the Marantec Garage Door integration.

The opener uses a single static RF code: each transmission triggers the door.
There is no position feedback, so the entity is optimistic and exposes only an
"open" action. Closing is performed by the door itself (auto-close), never by
Home Assistant, so no close, stop, or position controls are offered.

Pressing "open" transmits the code and then drives an assumed state machine:

    opening --(travel_up s)--> open --(auto_close_delay s)-->
        closing --(travel_down s)--> closed

When the travel times are 0 (the default) the opening/closing phases are
skipped, collapsing to: open --(auto_close_delay s)--> closed. The auto-close
delay is measured from the moment the door is assumed fully open.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import MarantecConfigEntry
from ._marantec import MarantecCommand
from .const import (
    CONF_AUTO_CLOSE_DELAY,
    CONF_CODE,
    CONF_TRANSMITTER,
    CONF_TRAVEL_DOWN,
    CONF_TRAVEL_UP,
    DEFAULT_AUTO_CLOSE_DELAY,
    DEFAULT_TRAVEL_TIME,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarantecConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Marantec garage cover from a config entry."""
    async_add_entities([MarantecCover(entry)])


class MarantecCover(CoverEntity):
    """A single-button, open-only, timed-optimistic Marantec garage door."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = CoverDeviceClass.GARAGE
    # Open is the only user action. Closing is the door's own auto-close.
    _attr_supported_features = CoverEntityFeature.OPEN
    _attr_assumed_state = True

    def __init__(self, entry: MarantecConfigEntry) -> None:
        """Initialize the cover from stored config."""
        self._code: int = entry.data[CONF_CODE]
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._auto_close_delay: int = entry.options.get(
            CONF_AUTO_CLOSE_DELAY, DEFAULT_AUTO_CLOSE_DELAY
        )
        self._travel_up: int = entry.options.get(CONF_TRAVEL_UP, DEFAULT_TRAVEL_TIME)
        self._travel_down: int = entry.options.get(
            CONF_TRAVEL_DOWN, DEFAULT_TRAVEL_TIME
        )
        self._attr_unique_id = entry.entry_id

        # Assumed state. Closed on boot: no feedback, and the door auto-closes,
        # so closed is the safe assumption after any restart.
        self._closed = True
        self._opening = False
        self._closing = False
        self._cancel_timer: Callable[[], None] | None = None

    @property
    def is_closed(self) -> bool:
        """Return True if the door is assumed fully closed."""
        return self._closed

    @property
    def is_opening(self) -> bool:
        """Return True while the door is assumed to be opening."""
        return self._opening

    @property
    def is_closing(self) -> bool:
        """Return True while the door is assumed to be closing."""
        return self._closing

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Trigger the opener and start the assumed open/auto-close cycle."""
        command = MarantecCommand(code=self._code)
        await async_send_command(self.hass, self._transmitter, command)
        self._cancel_pending_timer()
        self._begin_opening()

    @callback
    def _begin_opening(self) -> None:
        """Enter the opening phase, or jump to open if no travel time."""
        if self._travel_up > 0:
            self._set_state(closed=False, opening=True, closing=False)
            self._schedule(self._travel_up, self._reach_open)
        else:
            self._reach_open(None)

    @callback
    def _reach_open(self, _now: Any) -> None:
        """Door is assumed fully open; start the auto-close delay."""
        self._set_state(closed=False, opening=False, closing=False)
        if self._auto_close_delay > 0:
            self._schedule(self._auto_close_delay, self._begin_closing)

    @callback
    def _begin_closing(self, _now: Any) -> None:
        """Enter the closing phase, or jump to closed if no travel time."""
        if self._travel_down > 0:
            self._set_state(closed=False, opening=False, closing=True)
            self._schedule(self._travel_down, self._reach_closed)
        else:
            self._reach_closed(None)

    @callback
    def _reach_closed(self, _now: Any) -> None:
        """Door is assumed fully closed."""
        self._set_state(closed=True, opening=False, closing=False)

    @callback
    def _schedule(self, delay: int, action: Callable[[Any], None]) -> None:
        """Schedule the next phase transition, replacing any pending one."""
        self._cancel_pending_timer()
        self._cancel_timer = async_call_later(self.hass, delay, action)

    @callback
    def _set_state(self, *, closed: bool, opening: bool, closing: bool) -> None:
        """Update the assumed state and write it to Home Assistant."""
        self._closed = closed
        self._opening = opening
        self._closing = closing
        self.async_write_ha_state()

    @callback
    def _cancel_pending_timer(self) -> None:
        """Cancel a scheduled phase transition, if any."""
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    async def async_will_remove_from_hass(self) -> None:
        """Clean up any pending timer when the entity is removed."""
        self._cancel_pending_timer()
