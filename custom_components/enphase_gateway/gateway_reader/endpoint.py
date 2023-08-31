"""Module containing Gateway Endpoint constansts and classes"""

import time


ENDPOINT_URL_PRODUCTION_JSON = "{}://{}/production.json"
ENDPOINT_URL_PRODUCTION_V1 = "{}://{}/api/v1/production"
ENDPOINT_URL_PRODUCTION_INVERTERS = "{}://{}/api/v1/production/inverters"
ENDPOINT_URL_PRODUCTION = "{}://{}/production"
ENDPOINT_URL_CHECK_JWT = "https://{}/auth/check_jwt"
ENDPOINT_URL_ENSEMBLE_INVENTORY = "{}://{}/ivp/ensemble/inventory"
ENDPOINT_URL_ENSEMBLE_SUBMOD = "{}://{}/ivp/ensemble/submod"
ENDPOINT_URL_ENSEMBLE_SECCTRL = "{}://{}/ivp/ensemble/secctrl"
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
    "ensemble_submod" : ENDPOINT_URL_ENSEMBLE_SUBMOD,
    "ensemble_secctrl" : ENDPOINT_URL_ENSEMBLE_SECCTRL,
    "ensemble_power": ENDPOINT_URL_ENSEMBLE_POWER,   
}


class GatewayEndpoint:
    """Class representing a Gateway endpoint."""

    def __init__(self, name: str, cache: int = 0):
        """Initialize instance of GatewayEndpoint.
        
        Parameters
        ----------
        name : str
            Unique name of the endpoint. Has to be one of ENDPOINTS.keys().
            The name is used as dict key to store results for this endpoint.
        cache : int, optional
            Number of seconds to cache this endpoint. 
            The default is 0.

        Returns
        -------
        None.

        """
        self.name = name
        self._url = "{}://{}/{}"
        self.cache = cache
        self.last_fetch = None

    def __repr__(self):
        """Magic method. Use name for representation."""
        return self.name

    @property
    def update_required(self) -> bool:
        """Check if an update is required for this endpoint.
        
        An update is required if the endpoint has not been updated before
        or the cache has expired.

        Returns
        -------
        bool
            Returns True if an update is required. False otherwise.

        """
        if not self.last_fetch:
            return True
        elif (self.last_fetch + self.cache) <= time.time():
            return True
        else:
            return False
    
    def get_url(self, protocol, host):
        """Return formatted url."""
        return self._url.format(protocol, host, self.name)
    
    def success(self, timestamp: float = None):
        """Call this method to update the last_fetch timestamp.        

        Parameters
        ----------
        timestamp : float, optional
            Time in seconds since the epoch. The default is None.

        Returns
        -------
        None.

        """
        if not timestamp:
            timestamp = time.time()
        self.last_fetch = timestamp
        
