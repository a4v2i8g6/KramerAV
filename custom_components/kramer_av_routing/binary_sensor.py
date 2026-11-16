"""Read-only Kramer output status, reported by a verified Protocol 3000 query."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .control_entity import KramerControlEntity
from .coordinator import KramerCoordinator


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: KramerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KramerControlBinarySensor(coordinator, spec)
        for spec in coordinator.capabilities.values() if spec.kind == "binary_sensor"
    )


class KramerControlBinarySensor(KramerControlEntity, BinarySensorEntity):
    def __init__(self, coordinator: KramerCoordinator, spec) -> None:
        super().__init__(coordinator, spec)
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.control_values.get(self.spec.key)
        return None if value is None else value == self.spec.true_value
