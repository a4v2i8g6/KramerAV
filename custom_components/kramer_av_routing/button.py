"""Buttons to recall only confirmed, already-saved device presets."""

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KramerCoordinator
from .protocol import KramerError


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: KramerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(KramerPresetRecallButton(coordinator, slot)
                       for slot in coordinator.saved_presets)


class KramerPresetRecallButton(CoordinatorEntity[KramerCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: KramerCoordinator, slot: int) -> None:
        super().__init__(coordinator)
        self.slot = slot
        self._attr_name = f"Recall preset {slot}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_recall_preset_{slot}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Kramer",
            model=coordinator.model,
            sw_version=coordinator.firmware_version or None,
        )

    @property
    def available(self) -> bool:
        return (super().available and self.coordinator.client.connected
                and self.slot in self.coordinator.saved_presets)

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_recall_preset(self.slot)
        except (KramerError, ValueError) as exc:
            raise HomeAssistantError(f"Failed to recall preset {self.slot}: {exc}") from exc
