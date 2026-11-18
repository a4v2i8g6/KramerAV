"""Protocol 2000 video/audio matrix adapter for shared Kramer AV HA entities."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging

from homeassistant.helpers.update_coordinator import UpdateFailed

from .capabilities import ControlSpec
from .const import FAMILY_P2000
from .coordinator import KramerCoordinator
from .protocol2000 import Kramer2000Client, Protocol2000Error, Frame2000, probe_protocol2000

_LOGGER = logging.getLogger(__name__)


class Kramer2000Coordinator(KramerCoordinator):
    """Legacy binary protocol using the same video selectors as Protocol 3000."""

    def __init__(self, hass, entry) -> None:
        super().__init__(hass, entry)
        self.family = FAMILY_P2000
        self.client = Kramer2000Client(
            entry.data["host"], int(entry.data["port"]),
            machine=int(entry.data.get("machine_id", 1)),
            on_message=self._handle_2000_message,
            on_disconnect=self._handle_disconnect,
        )
        self.audio_inputs = 0
        self.audio_outputs = 0
        self.audio_routes: dict[int, int] = {}
        self._audio_poll_good = False
        self.last_success: str | None = None
        self.last_error: str | None = None

    async def async_initialize(self) -> None:
        await self.client.connect()
        inputs, outputs = await probe_protocol2000(self.client)
        if self.inputs not in (0, inputs) or self.outputs not in (0, outputs):
            raise Protocol2000Error(
                f"Video matrix is {inputs}x{outputs}; manual counts do not match")
        self.inputs, self.outputs = inputs, outputs
        self.model = f"Protocol 2000 matrix (machine {self.client.machine})"
        self.protocol_version = "2000"
        try:
            ai = await self.client.command(62, 1, 2, timeout=1.5,
                                           matcher=lambda m: m.instruction == 62 and m.input == 1)
            ao = await self.client.command(62, 2, 2, timeout=1.5,
                                           matcher=lambda m: m.instruction == 62 and m.input == 2)
            if 1 <= ai.output <= 127 and 1 <= ao.output <= 127:
                # Only enable audio controls after a real status query.
                feedback = await self.client.command(6, 0, 1, timeout=1.5,
                                                     matcher=lambda m: m.instruction == 6 and m.input == 0)
                if 0 <= feedback.output <= ai.output:
                    self.audio_inputs, self.audio_outputs = ai.output, ao.output
                    self.audio_routes[1] = feedback.output
        except Protocol2000Error:
            _LOGGER.debug("No independent Protocol 2000 audio route support detected")
        try:
            state = await self.client.command(31, 0, 0, timeout=1.5,
                                              matcher=lambda m: m.instruction == 31 and m.input == 0)
            if state.output in (0, 1):
                spec = ControlSpec("front_panel_lock", "Front panel locked", "switch", "LOCK-FP", config=True)
                self.capabilities[spec.key] = spec
                self.control_values[spec.key] = state.output
        except Protocol2000Error:
            _LOGGER.debug("Panel lock status not supported")
        _LOGGER.info("Protocol 2000 verified: %dx%d video, %dx%d audio, machine %d",
                     self.inputs, self.outputs, self.audio_inputs, self.audio_outputs,
                     self.client.machine)

    def _handle_2000_message(self, frame: Frame2000) -> None:
        if frame.instruction == 1 and 1 <= frame.output <= self.outputs and 0 <= frame.input <= self.inputs:
            self.async_set_updated_data({**(self.data or {}), frame.output: frame.input})
        elif frame.instruction == 2 and 1 <= frame.output <= self.audio_outputs and 0 <= frame.input <= self.audio_inputs:
            self.audio_routes[frame.output] = frame.input
            self.async_update_listeners()
        elif frame.instruction == 31 and frame.output in (0, 1):
            self.control_values["front_panel_lock"] = frame.output
            self.async_update_listeners()

    async def _async_update_data(self) -> dict[int, int]:
        routes: dict[int, int] = {}
        try:
            for output in range(1, self.outputs + 1):
                status = await self.client.command(
                    5, 0, output,
                    matcher=lambda frame: frame.instruction == 5 and frame.input == 0)
                if status.output > self.inputs:
                    raise Protocol2000Error(f"Bad source {status.output} on video output {output}")
                routes[output] = status.output
            for output in range(1, self.audio_outputs + 1):
                try:
                    status = await self.client.command(
                        6, 0, output, timeout=1.5,
                        matcher=lambda frame: frame.instruction == 6 and frame.input == 0)
                    if status.output <= self.audio_inputs:
                        self.audio_routes[output] = status.output
                except Protocol2000Error:
                    self.audio_routes.pop(output, None)
            if "front_panel_lock" in self.capabilities:
                try:
                    status = await self.client.command(31, 0, 0, timeout=1.5)
                    if status.output in (0, 1):
                        self.control_values["front_panel_lock"] = status.output
                except Protocol2000Error:
                    self.control_values.pop("front_panel_lock", None)
            self.last_success = datetime.now(timezone.utc).isoformat()
            self.last_error = None
        except (OSError, asyncio.TimeoutError, Protocol2000Error) as exc:
            self.last_error = type(exc).__name__
            raise UpdateFailed(f"Protocol 2000 poll failed: {exc}") from exc
        return routes

    async def async_set_route(self, output: int, source: int) -> None:
        if not 1 <= output <= self.outputs or not 0 <= source <= self.inputs:
            raise ValueError("Video source/output outside device limits")
        reply = await self.client.command(
            1, source, output,
            matcher=lambda msg: (msg.instruction == 1 and msg.input == source and msg.output == output))
        if reply.input != source:
            raise Protocol2000Error("Video switch unconfirmed")
        await self.async_request_refresh()

    async def async_set_audio_route(self, output: int, source: int) -> None:
        if not 1 <= output <= self.audio_outputs or not 0 <= source <= self.audio_inputs:
            raise ValueError("Audio source/output outside device limits")
        await self.client.command(
            2, source, output,
            matcher=lambda msg: (msg.instruction == 2 and msg.input == source and msg.output == output))
        await self.async_request_refresh()

    async def async_set_control(self, key: str, value: int) -> None:
        if key != "front_panel_lock" or key not in self.capabilities or value not in (0, 1):
            raise ValueError("Unsupported Protocol 2000 control")
        await self.client.command(
            30, value, 0,
            matcher=lambda msg: msg.instruction == 30 and msg.input == value and msg.output == 0)
        self.control_values[key] = value
        self.async_update_listeners()
