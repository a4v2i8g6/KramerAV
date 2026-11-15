"""Device identification and live video routing for Protocol 3000 matrices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COMMAND_FAMILY,
    CONF_INPUTS,
    CONF_OUTPUTS,
    CONF_POLL_INTERVAL,
    CONF_TRANSPORT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    FAMILY_AUTO,
    FAMILY_ROUTE,
    FAMILY_VID,
    TRANSPORT_TCP,
)
from .protocol import (
    KramerClient,
    KramerConnectionError,
    KramerError,
    KramerMessage,
    parse_io_count,
    parse_route,
)

_LOGGER = logging.getLogger(__name__)


class KramerCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """One coordinator per Kramer device; one select entity per output."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        self.inputs = int(entry.data[CONF_INPUTS])
        self.outputs = int(entry.data[CONF_OUTPUTS])
        self.model = "Kramer Protocol 3000"
        self.protocol_version = ""
        self.firmware_version = ""
        self.family = entry.data[CONF_COMMAND_FAMILY]
        self.client = KramerClient(
            entry.data["host"],
            int(entry.data["port"]),
            entry.data.get(CONF_TRANSPORT, TRANSPORT_TCP),
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))),
        )

    async def async_initialize(self) -> None:
        """Discover identity and matrix capabilities using read-only queries."""
        await self.client.connect()
        model = await self.client.command("MODEL?")
        if not model.payload or model.command != "MODEL":
            raise KramerConnectionError("Device did not return a Protocol 3000 model")
        self.model = model.payload

        try:
            version = await self.client.command("PROT-VER?")
            self.protocol_version = version.payload
        except KramerError:
            _LOGGER.debug("PROT-VER? unavailable for %s", self.model)

        try:
            version = await self.client.command("VERSION?")
            self.firmware_version = version.payload
        except KramerError:
            _LOGGER.debug("VERSION? unavailable for %s", self.model)

        if not self.inputs or not self.outputs:
            try:
                count_msg = await self.client.command("INFO-IO?")
                counts = parse_io_count(count_msg)
                if counts:
                    if not self.inputs:
                        self.inputs = counts[0]
                    if not self.outputs:
                        self.outputs = counts[1]
            except KramerError:
                _LOGGER.debug("INFO-IO? unavailable for %s", self.model)
        if not (1 <= self.inputs <= 256 and 1 <= self.outputs <= 256):
            raise KramerConnectionError(
                "Unable to detect input/output count. Re-add this device with manual input/output counts."
            )

        if self.family == FAMILY_AUTO:
            for family in (FAMILY_ROUTE, FAMILY_VID):
                try:
                    response = await self.client.command(
                        self._query(family, 1),
                        matcher=lambda msg, f=family: 1 in parse_route(msg, f),
                    )
                    if 1 in parse_route(response, family):
                        self.family = family
                        break
                except KramerError:
                    continue
            if self.family == FAMILY_AUTO:
                raise KramerConnectionError(
                    "No supported video routing query (ROUTE?/VID?). Select a command family manually "
                    "or provide a device-specific profile."
                )
        _LOGGER.info(
            "Kramer %s connected over %s; %d inputs, %d outputs; routing family %s",
            self.model,
            self.client.transport,
            self.inputs,
            self.outputs,
            self.family,
        )

    @staticmethod
    def _query(family: str, output: int) -> str:
        if family == FAMILY_ROUTE:
            return f"ROUTE? 1,{output}"
        return f"VID? {output}"

    def _handle_message(self, message: KramerMessage) -> None:
        if self.family not in (FAMILY_ROUTE, FAMILY_VID):
            return
        routes = parse_route(message, self.family)
        if not routes:
            return
        valid = {
            out: src
            for out, src in routes.items()
            if 1 <= out <= self.outputs and 0 <= src <= self.inputs
        }
        if valid:
            self.async_set_updated_data({**(self.data or {}), **valid})

    def _handle_disconnect(self) -> None:
        # Mark all entities unavailable until the next successful poll.
        self.async_update_listeners()

    async def _async_update_data(self) -> dict[int, int]:
        routes: dict[int, int] = {}
        try:
            for output in range(1, self.outputs + 1):
                message = await self.client.command(
                    self._query(self.family, output),
                    matcher=lambda msg, out=output: out in parse_route(msg, self.family),
                )
                result = parse_route(message, self.family)
                routes[output] = result[output]
        except (KramerError, OSError, asyncio.TimeoutError) as exc:
            raise UpdateFailed(f"Kramer routing poll failed: {exc}") from exc
        return routes

    async def async_set_route(self, output: int, source: int) -> None:
        """Set one crosspoint and verify from feedback, never assume success."""
        if output < 1 or output > self.outputs or source < 0 or source > self.inputs:
            raise ValueError("Output/input number is outside the matrix layout")
        if self.family == FAMILY_ROUTE and source == 0:
            raise ValueError("Disconnect is only supported with the VID command family")
        if self.family == FAMILY_ROUTE:
            command = f"ROUTE 1,{output},{source}"
        else:
            command = f"VID {source}>{output}"
        reply = await self.client.command(
            command,
            matcher=lambda msg: parse_route(msg, self.family).get(output) == source,
        )
        if parse_route(reply, self.family).get(output) != source:
            raise KramerError(f"Device did not confirm {command}")
        await self.async_request_refresh()

    async def async_close(self) -> None:
        await self.client.close()
