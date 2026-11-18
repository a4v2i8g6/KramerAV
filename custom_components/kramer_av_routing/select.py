"""One input selector for every matrix/presentation output."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INPUT_NAMES, CONF_OUTPUT_NAMES, DOMAIN, FAMILY_VID, FAMILY_X_ROUTE, FAMILY_P2000
from .coordinator import KramerCoordinator
from .control_entity import KramerControlEntity
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
    entities = [
        KramerOutputSelect(coordinator, output, inputs, outputs[output - 1])
        for output in range(1, coordinator.outputs + 1)
    ]
    entities.extend(KramerControlSelect(coordinator, spec)
                    for spec in coordinator.capabilities.values() if spec.kind == "select")
    if coordinator.audio_outputs:
        audio_inputs = _friendly_names(
            entry.options.get(CONF_INPUT_NAMES, ""), coordinator.audio_inputs, "Input")
        entities.extend(
            KramerAudioSelect(coordinator, output, audio_inputs)
            for output in range(1, coordinator.audio_outputs + 1)
        )
    async_add_entities(entities)


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
        self._options = (["Disconnected"] if coordinator.family in (FAMILY_VID, FAMILY_P2000) else []) + inputs
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
            return "Disconnected" if self.coordinator.family in (FAMILY_VID, FAMILY_P2000) else None
        index = source - 1 + (1 if self.coordinator.family in (FAMILY_VID, FAMILY_P2000) else 0)
        return self._options[index] if index < len(self._options) else None

    async def async_select_option(self, option: str) -> None:
        """Send routing command; the device reply determines new state."""
        try:
            index = self._options.index(option)
        except ValueError as exc:
            raise HomeAssistantError(f"Unsupported input option {option!r}") from exc
        source = index if self.coordinator.family in (FAMILY_VID, FAMILY_P2000) else index + 1
        try:
            await self.coordinator.async_set_route(self.output, source)
        except Exception as exc:
            raise HomeAssistantError(f"Kramer route change failed: {exc}") from exc


class KramerControlSelect(KramerControlEntity, SelectEntity):
    """A non-routing selection for a verified scaler/device capability."""

    def __init__(self, coordinator: KramerCoordinator, spec) -> None:
        super().__init__(coordinator, spec)
        self._attr_options = [label for _, label in spec.choices]

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.control_values.get(self.spec.key)
        return self.spec.option_label(value) if value is not None else None

    async def async_select_option(self, option: str) -> None:
        value = self.spec.option_code(option)
        if value is None:
            raise HomeAssistantError(f"Unsupported option {option!r}")
        try:
            await self.coordinator.async_set_control(self.spec.key, value)
        except (KramerError, ValueError, KeyError) as exc:
            raise HomeAssistantError(f"Kramer control {self.spec.key} failed: {exc}") from exc


class KramerAudioSelect(CoordinatorEntity[KramerCoordinator], SelectEntity):
    """Independent audio crosspoint on a verified 2000 or 3000 matrix."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KramerCoordinator, output: int, inputs: list[str]):
        super().__init__(coordinator)
        self.output = output
        self._attr_name = f"Audio output {output} source"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_audio_output_{output}"
        self._attr_options = (["Disconnected"] if coordinator.family == FAMILY_P2000 else []) + inputs
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title, manufacturer="Kramer", model=coordinator.model,
        )

    @property
    def available(self) -> bool:
        return (super().available and self.coordinator.client.connected
                and self.output in self.coordinator.audio_routes)

    @property
    def current_option(self) -> str | None:
        source = self.coordinator.audio_routes.get(self.output)
        if source is None:
            return None
        if self.coordinator.family == FAMILY_P2000:
            return self._attr_options[source] if 0 <= source < len(self._attr_options) else None
        return self._attr_options[source - 1] if 1 <= source <= len(self._attr_options) else None

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            raise HomeAssistantError(f"Unsupported audio source: {option}")
        try:
            index = self._attr_options.index(option)
            source = index if self.coordinator.family == FAMILY_P2000 else index + 1
            await self.coordinator.async_set_audio_route(self.output, source)
        except Exception as exc:
            raise HomeAssistantError(f"Kramer audio switching failed: {exc}") from exc
