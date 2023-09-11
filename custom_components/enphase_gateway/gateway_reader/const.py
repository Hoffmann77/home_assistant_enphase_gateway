"""constants module."""

from awesomeversion import AwesomeVersion


LEGACY_ENVOY_VERSION = AwesomeVersion("3.9.0")

AVAILABLE_PROPERTIES = {
    "production", "daily_production", "seven_days_production",
    "lifetime_production", "consumption", "daily_consumption",
    "seven_days_consumption", "lifetime_consumption", "inverters_production",
    "grid_status", "ensemble_power", "ensemble_submod", "ensemble_secctrl",
    "battery_storage",
}
