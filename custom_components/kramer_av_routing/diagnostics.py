"""Privacy-preserving, read-only diagnostics for Home Assistant."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_PROTOCOL, PROTOCOL_3000


def diagnostics_snapshot(entry: ConfigEntry, coordinator) -> dict:
    """Never export hostnames, IPs, device names, credentials or raw packets."""
    return {
        "integration_version": "0.6.0-alpha",
        "protocol": entry.data.get(CONF_PROTOCOL, PROTOCOL_3000),
        "transport": entry.data.get("transport"),
        "port": entry.data.get("port"),
        "machine_id": entry.data.get("machine_id") if entry.data.get(CONF_PROTOCOL) == "2000" else None,
        "device_model": coordinator.model,
        "protocol_version": coordinator.protocol_version,
        "firmware_version": coordinator.firmware_version,
        "routing_family": coordinator.family,
        "profile": coordinator.profile.model if coordinator.profile else None,
        "video_inputs": coordinator.inputs,
        "video_outputs": coordinator.outputs,
        "audio_inputs": coordinator.audio_inputs,
        "audio_outputs": coordinator.audio_outputs,
        "connected_socket": coordinator.client.connected,
        "last_poll_success": coordinator.last_update_success,
        "last_successful_poll": coordinator.last_success,
        "last_error_type": coordinator.last_error,
        "supported_controls": sorted(coordinator.capabilities),
        "saved_preset_count": len(coordinator.saved_presets),
        "routing_state": dict(coordinator.data or {}),
        "audio_routing_state": dict(coordinator.audio_routes),
    }


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Diagnostics can be downloaded from the Home Assistant integration UI."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return diagnostics_snapshot(entry, coordinator)
