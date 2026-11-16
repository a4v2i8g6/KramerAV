"""Constants for Kramer AV Routing."""

from homeassistant.const import Platform

DOMAIN = "kramer_av_routing"
DEFAULT_PORT_TCP = 5000
DEFAULT_PORT_UDP = 50000
DEFAULT_POLL_INTERVAL = 30
DEFAULT_TIMEOUT = 4.0

CONF_TRANSPORT = "transport"
CONF_INPUTS = "inputs"
CONF_OUTPUTS = "outputs"
CONF_COMMAND_FAMILY = "command_family"
CONF_PROFILE_MODE = "profile_mode"
PROFILE_AUTO = "auto"
PROFILE_GENERIC = "generic"
CONF_INPUT_NAMES = "input_names"
CONF_OUTPUT_NAMES = "output_names"
CONF_POLL_INTERVAL = "poll_interval"

TRANSPORT_TCP = "tcp"
TRANSPORT_UDP = "udp"
FAMILY_AUTO = "auto"
FAMILY_ROUTE = "route"
FAMILY_VID = "vid"
FAMILY_X_ROUTE = "x_route"

PLATFORMS = [
    Platform.SELECT, Platform.SWITCH, Platform.NUMBER, Platform.BINARY_SENSOR, Platform.BUTTON,
]
