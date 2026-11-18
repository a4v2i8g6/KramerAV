"""Read-only Kramer output status, reported by a verified Protocol 3000 query."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .control_entity import KramerControlEntity
from .coordinator import KramerCoordinator


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: KramerCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [KramerControlBinarySensor(coordinator, spec)
                for spec in coordinator.capabilities.values() if spec.kind == "binary_sensor"]
    entities.append(KramerConnectionBinarySensor(coordinator))
    async_add_entities(entities)


class KramerControlBinarySensor(KramerControlEntity, BinarySensorEntity):
    def __init__(self, coordinator: KramerCoordinator, spec) -> None:
        super().__init__(coordinator, spec)
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.control_values.get(self.spec.key)
        return None if value is None else value == self.spec.true_value


class KramerConnectionBinarySensor(CoordinatorEntity[KramerCoordinator], BinarySensorEntity):
    """Expose device responsiveness, not merely whether the local UDP socket exists."""
    _attr_has_entity_name = True
    _attr_name = "Connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: KramerCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_connection"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Kramer", model=coordinator.model,
        )

    @property
    def available(self) -> bool:
        # Otherwise Home Assistant hides "disconnected" by marking the sensor
        # unavailable whenever the coordinator reports a failed poll.
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.client.connected and self.coordinator.last_update_success)
