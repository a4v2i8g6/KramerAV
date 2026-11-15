"""UI configuration for Kramer Protocol 3000 AV routing devices."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
import voluptuous as vol

from .const import (
    CONF_COMMAND_FAMILY,
    CONF_INPUTS,
    CONF_INPUT_NAMES,
    CONF_OUTPUTS,
    CONF_PROFILE_MODE,
    PROFILE_AUTO,
    PROFILE_GENERIC,
    CONF_OUTPUT_NAMES,
    CONF_POLL_INTERVAL,
    CONF_TRANSPORT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT_TCP,
    DOMAIN,
    FAMILY_AUTO,
    FAMILY_ROUTE,
    FAMILY_VID,
    FAMILY_X_ROUTE,
    TRANSPORT_TCP,
    TRANSPORT_UDP,
)
from .protocol import KramerClient, KramerError


STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): vol.All(str, vol.Length(min=1)),
        vol.Required(CONF_PORT, default=DEFAULT_PORT_TCP): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_TRANSPORT, default=TRANSPORT_TCP): vol.In(
            [TRANSPORT_TCP, TRANSPORT_UDP]
        ),
        vol.Required(CONF_INPUTS, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=256)
        ),
        vol.Required(CONF_OUTPUTS, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=256)
        ),
        vol.Required(CONF_COMMAND_FAMILY, default=FAMILY_AUTO): vol.In(
            [FAMILY_AUTO, FAMILY_ROUTE, FAMILY_VID, FAMILY_X_ROUTE]
        ),
        vol.Required(CONF_PROFILE_MODE, default=PROFILE_AUTO): vol.In(
            [PROFILE_AUTO, PROFILE_GENERIC]
        ),
    }
)



class KramerAVRoutingFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a device entry after checking that Protocol 3000 responds."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            transport = user_input[CONF_TRANSPORT]
            port = user_input[CONF_PORT]
            client = KramerClient(host, port, transport)
            try:
                await client.connect()
                reply = await client.command("MODEL?")
                if reply.command != "MODEL" or not reply.payload:
                    errors["base"] = "not_protocol_3000"
                else:
                    await self.async_set_unique_id(f"{transport}:{host.lower()}:{port}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Kramer {reply.payload}",
                        data={**user_input, CONF_HOST: host},
                    )
            except KramerError:
                errors["base"] = "cannot_connect"
            finally:
                await client.close()
        return self.async_show_form(step_id="user", data_schema=STEP_SCHEMA, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return KramerAVRoutingOptionsFlow(config_entry)


class KramerAVRoutingOptionsFlow(config_entries.OptionsFlow):
    """Adjust input/output friendly names and poll interval."""

    def __init__(self, config_entry) -> None:
        self._configured_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self._configured_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INPUT_NAMES, default=options.get(CONF_INPUT_NAMES, "")
                    ): str,
                    vol.Optional(
                        CONF_OUTPUT_NAMES, default=options.get(CONF_OUTPUT_NAMES, "")
                    ): str,
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                }
            ),
        )
