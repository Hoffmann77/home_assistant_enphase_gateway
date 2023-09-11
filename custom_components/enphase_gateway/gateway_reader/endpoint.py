"""Module containing Gateway Endpoint constansts and classes"""

import time


# ENDPOINT_URL_PRODUCTION_JSON = "{}://{}/production.json"
# ENDPOINT_URL_PRODUCTION_V1 = "{}://{}/api/v1/production"
# ENDPOINT_URL_PRODUCTION_INVERTERS = "{}://{}/api/v1/production/inverters"
# ENDPOINT_URL_PRODUCTION = "{}://{}/production"
# ENDPOINT_URL_CHECK_JWT = "https://{}/auth/check_jwt"
# ENDPOINT_URL_ENSEMBLE_INVENTORY = "{}://{}/ivp/ensemble/inventory"
# ENDPOINT_URL_ENSEMBLE_SUBMOD = "{}://{}/ivp/ensemble/submod"
# ENDPOINT_URL_ENSEMBLE_SECCTRL = "{}://{}/ivp/ensemble/secctrl"
# ENDPOINT_URL_ENSEMBLE_POWER = "{}://{}/ivp/ensemble/power"
# ENDPOINT_URL_HOME_JSON = "{}://{}/home.json"
# ENDPOINT_URL_INFO_XML = "{}://{}/info.xml"

# ENDPOINTS = {
#     "info_xml": ENDPOINT_URL_INFO_XML,
#     "home_json": ENDPOINT_URL_HOME_JSON,
#     "production_json": ENDPOINT_URL_PRODUCTION_JSON,
#     "production_v1": ENDPOINT_URL_PRODUCTION_V1,
#     "production_legacy": ENDPOINT_URL_PRODUCTION,
#     "production_inverters": ENDPOINT_URL_PRODUCTION_INVERTERS,
#     "ensemble_inventory": ENDPOINT_URL_ENSEMBLE_INVENTORY,
#     "ensemble_submod" : ENDPOINT_URL_ENSEMBLE_SUBMOD,
#     "ensemble_secctrl" : ENDPOINT_URL_ENSEMBLE_SECCTRL,
#     "ensemble_power": ENDPOINT_URL_ENSEMBLE_POWER,
# }


class GatewayEndpoint:
    """Class representing a Gateway endpoint."""

    def __init__(self, endpoint_path: str, cache: int = 0) -> None:
        """Initialize instance of GatewayEndpoint."""
        self.path = endpoint_path
        self.cache = cache
        self._last_fetch = None
        self._base_url = "{}://{}/{}"

    def __repr__(self):
        """Magic method. Use path for representation."""
        return self.path

    @property
    def update_required(self) -> bool:
        """Check if an update is required for this endpoint."""
        if not self._last_fetch:
            return True
        elif (self._last_fetch + self.cache) <= time.time():
            return True
        else:
            return False

    def get_url(self, protocol, host):
        """Return formatted url."""
        return self._base_url.format(protocol, host, self.path)

    def success(self, timestamp: float = None):
        """Update the last_fetch timestamp."""
        if not timestamp:
            timestamp = time.time()
        self._last_fetch = timestamp
