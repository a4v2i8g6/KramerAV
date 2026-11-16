"""Numeric Protocol 3000 controls with verified model-specific units/ranges."""

from homeassistant.components.number import NumberEntity
from homeassistant.exceptions import HomeAssistantError

from .capabilities import ControlSpec
from .const import DOMAIN
from .control_entity import KramerControlEntity
from .coordinator import KramerCoordinator
from .protocol import KramerError


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: KramerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KramerControlNumber(coordinator, spec)
        for spec in coordinator.capabilities.values() if spec.kind == "number"
    )


class KramerControlNumber(KramerControlEntity, NumberEntity):
    def __init__(self, coordinator: KramerCoordinator, spec: ControlSpec) -> None:
        super().__init__(coordinator, spec)
        self._attr_native_min_value = float(spec.minimum)
        self._attr_native_max_value = float(spec.maximum)
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.control_values.get(self.spec.key)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        if not float(value).is_integer():
            raise HomeAssistantError("This Kramer control requires an integer value")
        try:
            await self.coordinator.async_set_control(self.spec.key, int(value))
        except (KramerError, ValueError, KeyError) as exc:
            raise HomeAssistantError(f"Kramer control {self.spec.key} failed: {exc}") from exc
