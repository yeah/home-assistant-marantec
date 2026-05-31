"""The Marantec Garage Door integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.COVER]

type MarantecConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: MarantecConfigEntry) -> bool:
    """Set up Marantec Garage Door from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarantecConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: MarantecConfigEntry
) -> None:
    """Reload the entry when its options change (e.g. auto-close delay)."""
    await hass.config_entries.async_reload(entry.entry_id)
