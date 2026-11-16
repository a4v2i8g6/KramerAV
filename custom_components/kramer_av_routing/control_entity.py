"""Common entity identity and availability for discovered device controls."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .capabilities import ControlSpec
from .const import DOMAIN
from .coordinator import KramerCoordinator


class KramerControlEntity(CoordinatorEntity[KramerCoordinator]):
    """A read-back verified Protocol 3000 control."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KramerCoordinator, spec: ControlSpec) -> None:
        super().__init__(coordinator)
        self.spec = spec
        self._attr_name = spec.name
        self._attr_entity_registry_enabled_default = spec.enabled_default
        self._attr_unique_id = f"{coordinator.entry.entry_id}_control_{spec.key}"
        if spec.config:
            self._attr_entity_category = EntityCategory.CONFIG
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
                and self.spec.key in self.coordinator.control_values)
