

import time


ENDPOINT_URL_PRODUCTION_JSON = "{}://{}/production.json"
ENDPOINT_URL_PRODUCTION_V1 = "{}://{}/api/v1/production"
ENDPOINT_URL_PRODUCTION_INVERTERS = "{}://{}/api/v1/production/inverters"
ENDPOINT_URL_PRODUCTION = "{}://{}/production"
ENDPOINT_URL_CHECK_JWT = "https://{}/auth/check_jwt"
ENDPOINT_URL_ENSEMBLE_INVENTORY = "{}://{}/ivp/ensemble/inventory"
ENDPOINT_URL_ENSEMBLE_POWER = "{}://{}/ivp/ensemble/power"
ENDPOINT_URL_HOME_JSON = "{}://{}/home.json"
ENDPOINT_URL_INFO_XML = "{}://{}/info.xml"


ENDPOINTS = {
    "info_xml": ENDPOINT_URL_INFO_XML,
    "home_json": ENDPOINT_URL_HOME_JSON,
    "production_json": ENDPOINT_URL_PRODUCTION_JSON,
    "production_v1": ENDPOINT_URL_PRODUCTION_V1,
    "production_legacy": ENDPOINT_URL_PRODUCTION,
    "production_inverters": ENDPOINT_URL_PRODUCTION_INVERTERS,
    "ensemble_inventory": ENDPOINT_URL_ENSEMBLE_INVENTORY,
    "ensemble_power": ENDPOINT_URL_ENSEMBLE_POWER,
}


class Endpoint:
    """Class representing a Gateway endpoint."""
    
    def __init__(self, name, cache=0):
        self.name = name
        self.url = ENDPOINTS.get(name)
        self.cache = cache
        self.last_fetch = None
    
    @property
    def update_required(self):
        """Return if the endpoints needs to be updated."""
        if not self.last_fetch:
            return True
        elif (self.last_fetch + self.cache) <= time.time():
            return True
        else:
            return False
        
    def updated(self, timestamp=None):
        """Update the timestamp of the last fetch."""
        if not timestamp:
            timestamp = time.time()
        self.last_fetch = timestamp