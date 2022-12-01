"""Constants for EnergyScore"""
# Base component constants
NAME = "EnergyScore"
DOMAIN = "energyscore"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ISSUE_URL = "https://github.com/knudsvik/energyscore/issues"

# Icons
ICON = "mdi:speedometer"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

# Configuration and options
CONF_PRICE_ENTITY = "price_entity"
CONF_ENERGY_ENTITY = "energy_entity"

# Defaults
DEFAULT_NAME = DOMAIN

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""