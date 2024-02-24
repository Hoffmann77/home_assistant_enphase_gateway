"""The enphase_envoy component."""

from homeassistant.const import Platform

from .gateway_reader.exceptions import (
    EnlightenAuthenticationError,
    EnlightenCommunicationError,
    GatewayAuthenticationError,
    GatewayCommunicationError,
)


DOMAIN = "enphase_gateway"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

ICON = "mdi:flash"

COORDINATOR = "coordinator"

NAME = "name"

DATA_UPDATE_INTERVAL = {
    "slow": 120,
    "moderate": 60,
    "fast": 30,
    "extra_fast": 15,
}

CONFIG_FLOW_USER_ERROR = (
    EnlightenAuthenticationError,
    EnlightenCommunicationError,
    GatewayAuthenticationError,
    GatewayCommunicationError,
)

AVAILABLE_PROPERTIES = {
    "production", "daily_production", "seven_days_production",
    "lifetime_production", "consumption", "daily_consumption",
    "seven_days_consumption", "lifetime_consumption", "inverters_production",
    "grid_status", "ensemble_power", "ensemble_submod", "ensemble_secctrl",
    "battery_storage", "encharge_inventory", "encharge_power"
}

ALLOWED_ENDPOINTS = [
    "info", "info.xml", "production", "api/v1/production", "production.json",
    "api/v1/production/inverters", "ivp/ensemble/inventory", "home.json",
    "ivp/ensemble/power", "ivp/ensemble/secctrl", "ivp/meters/readings",
    "auth/check_jwt" "ivp/meters",
]

CONF_SERIAL_NUM = "serial_num"
CONF_USE_TOKEN_AUTH = "use_token_auth"
CONF_TOKEN_RAW = "token_raw"
CONF_CACHE_TOKEN = "cache_token"
CONF_EXPOSE_TOKEN = "expose_token"
CONF_EXPOSURE_PATH = "exposure_path"
CONF_DATA_UPDATE_INTERVAL = "data_update_interval"
CONF_GET_INVERTERS = "get_inverters"
CONF_ENCHARGE_ENTITIES = "encharge_entities"
CONF_USE_LEGACY_NAME = "use_lagacy_name"
CONF_INVERTERS = "inverters_config"
