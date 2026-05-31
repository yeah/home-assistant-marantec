"""Constants for the Marantec Garage Door integration."""

from __future__ import annotations

DOMAIN = "marantec_garage"

# Config entry data keys.
CONF_CODE = "code"
CONF_TRANSMITTER = "transmitter"

# Config entry option keys (adjustable after setup).
CONF_AUTO_CLOSE_DELAY = "auto_close_delay"
CONF_TRAVEL_UP = "travel_up"
CONF_TRAVEL_DOWN = "travel_down"

# Marantec is a 49-bit static code.
CODE_BIT_COUNT = 49
CODE_MAX = (1 << CODE_BIT_COUNT) - 1

# Seconds the door is assumed to stay open before auto-closing, measured from
# the moment it is assumed fully open.
DEFAULT_AUTO_CLOSE_DELAY = 120

# Seconds the door takes to travel. 0 skips the opening/closing phases and the
# door transitions directly between open and closed.
DEFAULT_TRAVEL_TIME = 0
