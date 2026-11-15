"""Kramer AV Routing: Protocol 3000 matrix and presentation switcher control."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import KramerCoordinator
from .protocol import KramerError


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one Kramer device after read-only capability probing."""
    coordinator = KramerCoordinator(hass, entry)
    try:
        await coordinator.async_initialize()
        await coordinator.async_config_entry_first_refresh()
    except (KramerError, ConfigEntryNotReady) as exc:
        await coordinator.async_close()
        raise ConfigEntryNotReady(str(exc)) from exc

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload to apply changed labels and poll interval."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and close the network connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()
    return unloaded
