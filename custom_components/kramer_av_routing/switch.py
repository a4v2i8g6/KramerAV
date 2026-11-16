"""Boolean Protocol 3000 controls discovered using read-only probes."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from .capabilities import ControlSpec
from .const import DOMAIN
from .control_entity import KramerControlEntity
from .coordinator import KramerCoordinator
from .protocol import KramerError


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: KramerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KramerControlSwitch(coordinator, spec)
        for spec in coordinator.capabilities.values() if spec.kind == "switch"
    )


class KramerControlSwitch(KramerControlEntity, SwitchEntity):
    def __init__(self, coordinator: KramerCoordinator, spec: ControlSpec) -> None:
        super().__init__(coordinator, spec)

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.control_values.get(self.spec.key)
        return None if value is None else value == self.spec.true_value

    async def async_turn_on(self, **kwargs) -> None:
        await self._send(self.spec.true_value)

    async def async_turn_off(self, **kwargs) -> None:
        await self._send(self.spec.false_value)

    async def _send(self, value: int) -> None:
        try:
            await self.coordinator.async_set_control(self.spec.key, value)
        except (KramerError, ValueError, KeyError) as exc:
            raise HomeAssistantError(f"Kramer control {self.spec.key} failed: {exc}") from exc
