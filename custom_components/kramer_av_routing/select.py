"""One input selector for every matrix/presentation output."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INPUT_NAMES, CONF_OUTPUT_NAMES, DOMAIN, FAMILY_VID, FAMILY_X_ROUTE
from .coordinator import KramerCoordinator
from .protocol import KramerError


def _friendly_names(csv: str, count: int, prefix: str, defaults: tuple[str, ...] = ()) -> list[str]:
    """Produce unique, stable option labels even if names are duplicated."""
    supplied = [name.strip() for name in csv.split(",")]
    labels = []
    for index in range(1, count + 1):
        human = supplied[index - 1] if index <= len(supplied) else ""
        if not human and index <= len(defaults):
            human = defaults[index - 1]
        labels.append(f"{prefix} {index}" + (f" — {human}" if human else ""))
    return labels


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Create output selectors after the coordinator discovers the layout."""
    coordinator: KramerCoordinator = hass.data[DOMAIN][entry.entry_id]
    inputs = _friendly_names(
        entry.options.get(CONF_INPUT_NAMES, ""), coordinator.inputs, "Input",
        coordinator.profile.input_labels if coordinator.profile else (),
    )
    outputs = _friendly_names(
        entry.options.get(CONF_OUTPUT_NAMES, ""), coordinator.outputs, "Output",
        coordinator.profile.output_labels if coordinator.profile else (),
    )
    if coordinator.family == FAMILY_X_ROUTE:
        # Include physical connector identities, which may have overlapping numbers.
        inputs = [
            f"{label} ({signal.port_type} {signal.port_number})"
            for label, signal in zip(inputs, coordinator.x_inputs)
        ]
        outputs = [
            f"{label} ({signal.port_type} {signal.port_number})"
            for label, signal in zip(outputs, coordinator.x_outputs)
        ]
    async_add_entities(
        KramerOutputSelect(coordinator, output, inputs, outputs[output - 1])
        for output in range(1, coordinator.outputs + 1)
    )


class KramerOutputSelect(CoordinatorEntity[KramerCoordinator], SelectEntity):
    """Source selection for one physical output."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KramerCoordinator,
        output: int,
        inputs: list[str],
        output_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.output = output
        self._attr_name = output_name
        # Physical signal identity prevents entity IDs from shifting when a modular
        # chassis reports its ports in a different order after a firmware upgrade.
        if coordinator.family == FAMILY_X_ROUTE:
            port_key = str(coordinator.x_outputs[output - 1]).lower().replace(".", "_")
            self._attr_unique_id = f"{coordinator.entry.entry_id}_video_output_{port_key}"
        else:
            self._attr_unique_id = f"{coordinator.entry.entry_id}_video_output_{output}"
        self._options = (["Disconnected"] if coordinator.family == FAMILY_VID else []) + inputs
        self._attr_options = self._options
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Kramer",
            model=coordinator.model,
            sw_version=coordinator.firmware_version or None,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        """Expose the active routing backend and physical VP destination for debugging."""
        attributes: dict[str, str | int] = {"routing_family": self.coordinator.family}
        if self.coordinator.profile:
            attributes["device_profile"] = self.coordinator.profile.model
            attributes["route_layer"] = self.coordinator.profile.route_layer
            attributes["physical_output_id"] = self.coordinator.profile.output_ids[self.output - 1]
            route = (self.coordinator.data or {}).get(self.output)
            if route is not None and 1 <= route <= self.coordinator.inputs:
                attributes["physical_input_id"] = self.coordinator.profile.input_ids[route - 1]
        return attributes

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.connected

    @property
    def current_option(self) -> str | None:
        source = (self.coordinator.data or {}).get(self.output)
        if source is None:
            return None
        if source == 0:
            return "Disconnected" if self.coordinator.family == FAMILY_VID else None
        index = source - 1 + (1 if self.coordinator.family == FAMILY_VID else 0)
        return self._options[index] if index < len(self._options) else None

    async def async_select_option(self, option: str) -> None:
        """Send routing command; the device reply determines new state."""
        try:
            index = self._options.index(option)
        except ValueError as exc:
            raise HomeAssistantError(f"Unsupported input option {option!r}") from exc
        source = index if self.coordinator.family == FAMILY_VID else index + 1
        try:
            await self.coordinator.async_set_route(self.output, source)
        except (KramerError, ValueError) as exc:
            raise HomeAssistantError(f"Kramer route change failed: {exc}") from exc
