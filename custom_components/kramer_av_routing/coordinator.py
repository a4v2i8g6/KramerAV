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
    CONF_PROFILE_MODE,
    PROFILE_GENERIC,
    CONF_POLL_INTERVAL,
    CONF_TRANSPORT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    FAMILY_AUTO,
    FAMILY_ROUTE,
    FAMILY_VID,
    FAMILY_X_ROUTE,
    TRANSPORT_TCP,
)
from .profiles import VPProfile, profile_for_model
from .protocol import (
    KramerClient,
    KramerConnectionError,
    KramerError,
    KramerMessage,
    SignalId,
    parse_io_count,
    parse_route,
    parse_signals_list,
    parse_x_route,
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
        self.profile: VPProfile | None = None
        # Extended Protocol 3000 uses typed signal IDs, not contiguous port numbers.
        self.x_inputs: list[SignalId] = []
        self.x_outputs: list[SignalId] = []
        self._x_input_index: dict[SignalId, int] = {}
        self._x_output_index: dict[SignalId, int] = {}
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

        if self.family in (FAMILY_AUTO, FAMILY_X_ROUTE):
            await self._discover_extended_routing()

        # A matching VP profile must be verified by a read-only route query.
        # Never silently assume generic 1-based numbering for a known VP model.
        if (self.family in (FAMILY_AUTO, FAMILY_ROUTE)
                and self.entry.data.get(CONF_PROFILE_MODE, "auto") != PROFILE_GENERIC):
            profile = profile_for_model(self.model)
            if profile is not None:
                await self._activate_vp_profile(profile)

        if self.family != FAMILY_X_ROUTE and self.profile is None:
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
                        "No supported routing query (X-ROUTE?/ROUTE?/VID?). "
                        "Select a command family manually or provide a device-specific profile."
                    )
        _LOGGER.info(
            "Kramer %s connected over %s; %d inputs, %d outputs; routing family %s",
            self.model,
            self.client.transport,
            self.inputs,
            self.outputs,
            self.family,
        )

    async def _activate_vp_profile(self, profile: VPProfile) -> None:
        """Verify the exact model's physical routing IDs without changing it."""
        if self.inputs not in (0, len(profile.input_ids)) or self.outputs not in (
            0, len(profile.output_ids)
        ):
            raise KramerConnectionError(
                f"{profile.model} profile expects {len(profile.input_ids)} inputs and "
                f"{len(profile.output_ids)} logical outputs. Use automatic counts "
                "(0), or select Generic profile mode for explicit overrides."
            )

        destination = profile.output_ids[0]
        try:
            response = await self.client.command(
                f"ROUTE? {profile.route_layer},{destination}",
                matcher=lambda msg: (
                    (routes := parse_route(msg, FAMILY_ROUTE, layer=profile.route_layer))
                    .get(destination) in profile.input_ids
                ),
            )
        except KramerError as exc:
            raise KramerConnectionError(
                f"The documented ROUTE query for {profile.model} was not confirmed: {exc}. "
                "Check firmware/manual or select Generic profile mode to use manual routing settings."
            ) from exc
        if parse_route(response, FAMILY_ROUTE, layer=profile.route_layer).get(destination) not in profile.input_ids:
            raise KramerConnectionError("Profile ROUTE query returned an unrecognized source")

        self.profile = profile
        self.inputs = len(profile.input_ids)
        self.outputs = len(profile.output_ids)
        self.family = FAMILY_ROUTE
        _LOGGER.info("Verified %s VP routing profile (layer %s)", profile.model, profile.route_layer)

    async def _discover_extended_routing(self) -> None:
        """Probe X-ROUTE read-only; do not assume every listed signal is routable."""
        try:
            reply = await self.client.command("SIGNALS-LIST?")
            signals = parse_signals_list(reply)
            inputs = [
                signal for signal in signals
                if signal.direction == "IN" and signal.signal_type == "VIDEO"
            ]
            outputs = [
                signal for signal in signals
                if signal.direction == "OUT" and signal.signal_type == "VIDEO"
            ]
            if not (1 <= len(inputs) <= 256 and 1 <= len(outputs) <= 256):
                raise KramerConnectionError("SIGNALS-LIST? returned no usable video input/output pairs")

            # Verify one actual X-ROUTE query before committing to this family.
            candidate_output = outputs[0]
            response = await self.client.command(
                f"X-ROUTE? {candidate_output}",
                matcher=lambda msg: (
                    (pair := parse_x_route(msg)) is not None
                    and pair[0] == candidate_output
                    and pair[1] in inputs
                ),
            )
            if parse_x_route(response) is None:
                raise KramerConnectionError("X-ROUTE? did not return a valid video crosspoint")
        except KramerError as exc:
            if self.family == FAMILY_X_ROUTE:
                raise KramerConnectionError(f"X-ROUTE unsupported or unavailable: {exc}") from exc
            _LOGGER.debug("Extended routing unavailable for %s: %s", self.model, exc)
            return

        self.x_inputs = inputs
        self.x_outputs = outputs
        self._x_input_index = {signal: index for index, signal in enumerate(inputs, 1)}
        self._x_output_index = {signal: index for index, signal in enumerate(outputs, 1)}
        self.inputs, self.outputs = len(inputs), len(outputs)
        self.family = FAMILY_X_ROUTE
        _LOGGER.debug(
            "Detected X-ROUTE with video inputs %s and outputs %s",
            [str(s) for s in inputs],
            [str(s) for s in outputs],
        )

    def _query(self, family: str, output: int) -> str:
        if family == FAMILY_X_ROUTE:
            return f"X-ROUTE? {self.x_outputs[output - 1]}"
        if family == FAMILY_ROUTE:
            if self.profile:
                return f"ROUTE? {self.profile.route_layer},{self.profile.output_ids[output - 1]}"
            return f"ROUTE? 1,{output}"
        return f"VID? {output}"

    def _routes_from_message(self, message: KramerMessage, family: str) -> dict[int, int]:
        if family == FAMILY_X_ROUTE:
            pair = parse_x_route(message)
            if pair is None:
                return {}
            destination, source = pair
            output = self._x_output_index.get(destination)
            input_id = self._x_input_index.get(source)
            if output is None or input_id is None:
                return {}
            return {output: input_id}
        if family == FAMILY_ROUTE and self.profile:
            physical = parse_route(message, family, layer=self.profile.route_layer)
            input_lookup = {port: number for number, port in enumerate(self.profile.input_ids, 1)}
            output_lookup = {port: number for number, port in enumerate(self.profile.output_ids, 1)}
            return {
                output_lookup[dest]: input_lookup[source]
                for dest, source in physical.items()
                if dest in output_lookup and source in input_lookup
            }
        return parse_route(message, family)

    def _handle_message(self, message: KramerMessage) -> None:
        if self.family not in (FAMILY_ROUTE, FAMILY_VID, FAMILY_X_ROUTE):
            return
        routes = self._routes_from_message(message, self.family)
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
                    matcher=lambda msg, out=output: out in self._routes_from_message(msg, self.family),
                )
                result = self._routes_from_message(message, self.family)
                routes[output] = result[output]
        except (KramerError, OSError, asyncio.TimeoutError) as exc:
            raise UpdateFailed(f"Kramer routing poll failed: {exc}") from exc
        return routes

    async def async_set_route(self, output: int, source: int) -> None:
        """Set one crosspoint and verify from feedback, never assume success."""
        if output < 1 or output > self.outputs or source < 0 or source > self.inputs:
            raise ValueError("Output/input number is outside the matrix layout")
        if self.family != FAMILY_VID and source == 0:
            raise ValueError("Disconnect is only supported with the VID command family")
        if self.family == FAMILY_ROUTE:
            if self.profile:
                physical_output = self.profile.output_ids[output - 1]
                physical_source = self.profile.input_ids[source - 1]
                command = f"ROUTE {self.profile.route_layer},{physical_output},{physical_source}"
            else:
                command = f"ROUTE 1,{output},{source}"
        elif self.family == FAMILY_X_ROUTE:
            command = f"X-ROUTE {self.x_outputs[output - 1]},{self.x_inputs[source - 1]}"
        else:
            command = f"VID {source}>{output}"
        reply = await self.client.command(
            command,
            matcher=lambda msg: self._routes_from_message(msg, self.family).get(output) == source,
        )
        if self._routes_from_message(reply, self.family).get(output) != source:
            raise KramerError(f"Device did not confirm {command}")
        await self.async_request_refresh()

    async def async_close(self) -> None:
        await self.client.close()
