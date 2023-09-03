"""The enphase_envoy component."""

from homeassistant.const import Platform


DOMAIN = "enphase_gateway"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

ICON = "mdi:flash"

COORDINATOR = "coordinator"
NAME = "name"

AVAILABLE_PROPERTIES = {
    "production", "daily_production", "seven_days_production",
    "lifetime_production", "consumption", "daily_consumption",
    "seven_days_consumption", "lifetime_consumption", "inverters_production",
    "grid_status", "ensemble_power", "ensemble_submod", "ensemble_secctrl", 
    "battery_storage", "encharge_inventory", "encharge_power"
}

CONF_SERIAL_NUM = "serial_num"
CONF_USE_TOKEN_AUTH = "use_token_auth"
CONF_TOKEN_RAW = "token_raw"
CONF_CACHE_TOKEN = "cache_token"
CONF_EXPOSE_TOKEN = "expose_token"
CONF_EXPOSURE_PATH = "exposure_path"
CONF_GET_INVERTERS = "get_inverters"
CONF_ENCHARGE_ENTITIES = "storage_entities"
CONF_USE_LEGACY_NAME = "use_lagacy_name"



