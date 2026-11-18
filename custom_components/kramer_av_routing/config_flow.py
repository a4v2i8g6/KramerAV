"""UI setup and reconfiguration for Kramer AV Protocol 2000 / 3000."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
import voluptuous as vol

from .const import (
    CONF_COMMAND_FAMILY, CONF_INPUTS, CONF_INPUT_NAMES, CONF_OUTPUTS,
    CONF_PROFILE_MODE, PROFILE_AUTO, PROFILE_GENERIC, CONF_OUTPUT_NAMES,
    CONF_POLL_INTERVAL, CONF_TRANSPORT, DEFAULT_POLL_INTERVAL, DEFAULT_PORT_TCP,
    DEFAULT_PORT_UDP, DOMAIN, FAMILY_AUTO, FAMILY_ROUTE, FAMILY_VID,
    FAMILY_X_ROUTE, TRANSPORT_TCP, TRANSPORT_UDP,
    CONF_PROTOCOL, PROTOCOL_AUTO, PROTOCOL_2000, PROTOCOL_3000, CONF_MACHINE_ID,
)
from .protocol import KramerClient, KramerError
from .protocol2000 import Kramer2000Client, Protocol2000Error, probe_protocol2000


def setup_schema(defaults: dict | None = None) -> vol.Schema:
    """0 means use the default port for the chosen transport (avoids UDP 5000)."""
    values = defaults or {}
    return vol.Schema({
        vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): vol.All(str, vol.Length(min=1)),
        vol.Required(CONF_PROTOCOL, default=values.get(CONF_PROTOCOL, PROTOCOL_AUTO)):
            vol.In([PROTOCOL_AUTO, PROTOCOL_3000, PROTOCOL_2000]),
        vol.Required(CONF_TRANSPORT, default=values.get(CONF_TRANSPORT, TRANSPORT_TCP)):
            vol.In([TRANSPORT_TCP, TRANSPORT_UDP]),
        vol.Required(CONF_PORT, default=values.get(CONF_PORT, 0)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        vol.Required(CONF_MACHINE_ID, default=values.get(CONF_MACHINE_ID, 1)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
        vol.Required(CONF_INPUTS, default=values.get(CONF_INPUTS, 0)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=256)),
        vol.Required(CONF_OUTPUTS, default=values.get(CONF_OUTPUTS, 0)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=256)),
        vol.Required(CONF_COMMAND_FAMILY, default=values.get(CONF_COMMAND_FAMILY, FAMILY_AUTO)):
            vol.In([FAMILY_AUTO, FAMILY_ROUTE, FAMILY_VID, FAMILY_X_ROUTE]),
        vol.Required(CONF_PROFILE_MODE, default=values.get(CONF_PROFILE_MODE, PROFILE_AUTO)):
            vol.In([PROFILE_AUTO, PROFILE_GENERIC]),
    })


async def identify_device(data: dict) -> tuple[str, str, dict]:
    """Identify via strictly read-only requests, never change the protocol mode."""
    host, transport, port = data[CONF_HOST].strip(), data[CONF_TRANSPORT], int(data[CONF_PORT])
    if not host:
        raise ValueError("Host must not be empty")
    protocol = data[CONF_PROTOCOL]
    if protocol == PROTOCOL_2000 and transport != TRANSPORT_TCP:
        raise ValueError("Protocol 2000 currently supports TCP only")
    if protocol in (PROTOCOL_AUTO, PROTOCOL_3000):
        client = KramerClient(host, port, transport, timeout=3.0)
        try:
            await client.connect()
            reply = await client.command("MODEL?")
            if reply.command == "MODEL" and reply.payload:
                return PROTOCOL_3000, reply.payload, data
            if protocol == PROTOCOL_3000:
                raise ValueError("No valid Protocol 3000 MODEL response")
        except KramerError:
            if protocol == PROTOCOL_3000 or transport == TRANSPORT_UDP:
                raise
        finally:
            await client.close()
    if transport != TRANSPORT_TCP:
        raise ValueError("Protocol 2000 over UDP is not implemented")
    client2000 = Kramer2000Client(host, port, machine=int(data[CONF_MACHINE_ID]), timeout=3.0)
    try:
        await client2000.connect()
        inputs, outputs = await probe_protocol2000(client2000)
        if data[CONF_INPUTS] not in (0, inputs) or data[CONF_OUTPUTS] not in (0, outputs):
            raise ValueError("Manual I/O counts differ from detected Protocol 2000 device")
        return PROTOCOL_2000, f"Protocol 2000 {inputs}x{outputs} (machine {client2000.machine})", data
    finally:
        await client2000.close()


class KramerAVRoutingFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            if int(data[CONF_PORT]) == 0:
                data[CONF_PORT] = DEFAULT_PORT_UDP if data[CONF_TRANSPORT] == TRANSPORT_UDP else DEFAULT_PORT_TCP
            try:
                protocol, model, data = await identify_device(data)
                data[CONF_PROTOCOL] = protocol
                # Keep legacy 3000 unique IDs compatible with existing installations.
                uid = (f"{data[CONF_TRANSPORT]}:{data[CONF_HOST].lower()}:{data[CONF_PORT]}"
                       if protocol == PROTOCOL_3000 else
                       f"2000:tcp:{data[CONF_HOST].lower()}:{data[CONF_PORT]}:{data[CONF_MACHINE_ID]}")
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
                # Older versions used a transport+host+port derived ID.
                # A reconfigured entry can retain its original ID, so also
                # check actual endpoints to avoid duplicate device entries.
                if any(other.data.get(CONF_HOST) == data[CONF_HOST]
                       and other.data.get(CONF_PORT) == data[CONF_PORT]
                       and other.data.get(CONF_TRANSPORT) == data[CONF_TRANSPORT]
                       and other.data.get(CONF_PROTOCOL, PROTOCOL_3000) == protocol
                       and (protocol != PROTOCOL_2000 or other.data.get(CONF_MACHINE_ID, 1) == data[CONF_MACHINE_ID])
                       for other in self.hass.config_entries.async_entries(DOMAIN)):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(title=f"Kramer {model}", data=data)
            except (KramerError, Protocol2000Error, OSError):
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_configuration"
        return self.async_show_form(step_id="user", data_schema=setup_schema(), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        """Update network settings without deleting the HA config entry.

        Keep the existing unique ID; old versions derive it from IP/port rather
        than immutable hardware identity. Only permit the same protocol and a
        matching Protocol 3000 MODEL? identity, or matching Protocol 2000 layout.
        """
        entry = self._get_reconfigure_entry()
        defaults = {**entry.data, CONF_PROTOCOL: entry.data.get(CONF_PROTOCOL, PROTOCOL_3000)}
        errors = {}
        if user_input is not None:
            data = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            if not data[CONF_PORT]:
                data[CONF_PORT] = DEFAULT_PORT_UDP if data[CONF_TRANSPORT] == TRANSPORT_UDP else DEFAULT_PORT_TCP
            if data[CONF_PROTOCOL] in (PROTOCOL_AUTO, entry.data.get(CONF_PROTOCOL, PROTOCOL_3000)):
                data[CONF_PROTOCOL] = entry.data.get(CONF_PROTOCOL, PROTOCOL_3000)
                try:
                    protocol, model, data = await identify_device(data)
                    if protocol != entry.data.get(CONF_PROTOCOL, PROTOCOL_3000):
                        errors["base"] = "wrong_device"
                    elif protocol == PROTOCOL_3000 and entry.title != f"Kramer {model}":
                        errors["base"] = "wrong_device"
                    elif protocol == PROTOCOL_2000 and entry.title != f"Kramer {model}":
                        errors["base"] = "wrong_device"
                    elif any(other.entry_id != entry.entry_id
                             and other.data.get(CONF_HOST) == data[CONF_HOST]
                             and other.data.get(CONF_PORT) == data[CONF_PORT]
                             and other.data.get(CONF_TRANSPORT) == data[CONF_TRANSPORT]
                             for other in self.hass.config_entries.async_entries(DOMAIN)):
                        errors["base"] = "already_configured"
                    else:
                        return self.async_update_reload_and_abort(entry, data_updates=data)
                except (KramerError, Protocol2000Error, OSError, ValueError):
                    errors["base"] = "cannot_connect"
            else:
                errors["base"] = "protocol_change_not_supported"
        return self.async_show_form(step_id="reconfigure", data_schema=setup_schema(defaults), errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return KramerAVRoutingOptionsFlow(config_entry)


class KramerAVRoutingOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self._configured_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self._configured_entry.options
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Optional(CONF_INPUT_NAMES, default=options.get(CONF_INPUT_NAMES, "")): str,
            vol.Optional(CONF_OUTPUT_NAMES, default=options.get(CONF_OUTPUT_NAMES, "")): str,
            vol.Required(CONF_POLL_INTERVAL, default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
        }))
