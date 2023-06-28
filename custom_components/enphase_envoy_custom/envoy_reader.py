"""Module to read production and consumption values from an Enphase Envoy on the local network."""
import argparse
import asyncio
import logging
import re
import time
from json.decoder import JSONDecodeError

import httpx
from envoy_utils.envoy_utils import EnvoyUtils
from homeassistant.util.network import is_ipv6_address

from .enphase_token import EnphaseToken


#
# Legacy parser is only used on ancient firmwares
#
PRODUCTION_REGEX = r"<td>Currentl.*</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(W|kW|MW)</td>"
DAY_PRODUCTION_REGEX = r"<td>Today</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>"
WEEK_PRODUCTION_REGEX = (
    r"<td>Past Week</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>"
)
LIFE_PRODUCTION_REGEX = (
    r"<td>Since Installation</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>"
)
SERIAL_REGEX = re.compile(r"Envoy\s*Serial\s*Number:\s*([0-9]+)")

# Endpoint urls
ENDPOINT_URL_PRODUCTION_JSON = "{}://{}/production.json"
ENDPOINT_URL_PRODUCTION_V1 = "{}://{}/api/v1/production"
ENDPOINT_URL_PRODUCTION_INVERTERS = "{}://{}/api/v1/production/inverters"
ENDPOINT_URL_PRODUCTION = "{}://{}/production"
ENDPOINT_URL_CHECK_JWT = "https://{}/auth/check_jwt"
ENDPOINT_URL_ENSEMBLE_INVENTORY = "{}://{}/ivp/ensemble/inventory"
ENDPOINT_URL_HOME_JSON = "{}://{}/home.json"

_LOGGER = logging.getLogger(__name__)

GATEWAY_ENDPOINTS = {
    'ENVOY_MODEL_S_METERED': {
        "production_json": ENDPOINT_URL_PRODUCTION_JSON,
        "ensemble_json": ENDPOINT_URL_ENSEMBLE_INVENTORY,
        "home_json": ENDPOINT_URL_HOME_JSON,
    },
    'ENVOY_MODEL_S_STANDARD': {
        "production_json": ENDPOINT_URL_PRODUCTION_JSON,
        "ensemble_json": ENDPOINT_URL_ENSEMBLE_INVENTORY,
        "production_v1": ENDPOINT_URL_PRODUCTION_V1,
        "home_json": ENDPOINT_URL_HOME_JSON,
    },
    'ENVOY_MODEL_C': {
        "production_v1": ENDPOINT_URL_PRODUCTION_V1,
    },
    'ENVOY_MODEL_LEGACY': {
        "production_legacy": ENDPOINT_URL_PRODUCTION,
    }
}

# Endpoints used to detect the Envoy Model.
GATEWAY_DETECTION_ENDPOINTS = {
    "ENVOY_MODEL_S": {
        "production_json": ENDPOINT_URL_PRODUCTION_JSON,
    },
    "ENVOY_MODEL_C": {
        "production_v1": ENDPOINT_URL_PRODUCTION_V1,
    },
    "ENVOY_MODEL_LEGACY": {
        "production": ENDPOINT_URL_PRODUCTION,
    }
}


def has_production_and_consumption(json):
    """Check if json has keys for both production and consumption."""
    return "production" in json and "consumption" in json


def has_metering_setup(json):
    """Check if Active Count of Production CTs (eim) installed is greater than one."""
    return True if json["production"][1]["activeCount"] > 0 else False


class SwitchToHTTPS(Exception):
    """Switch to https exception."""
    
    pass


class EnvoyReader:
    """Instance of EnvoyReader."""

    messages = {
        "daily_production_not_available": 
            "Daily production data not available for your Envoy device.",
        "seven_day_production_not_available": 
            "Seven day production data not available for your Envoy device.",
        "battery_not_available":
            "Battery storage data not available for your Envoy device.",
        "consumption_not_available": 
            "Consumption data not available for your Envoy device.",
        "grid_status_not_available": 
            "Grid status not available for your Envoy device.",
    }

    def __init__(
        self,
        host,
        username="envoy",
        password="",
        gateway_serial_num=None,
        use_token_auth=False,
        token_filepath=None,
        inverters=False,
        async_client=None,
    ):
        """Init the EnvoyReader."""
        self.host = host.lower()
        if is_ipv6_address(self.host):
            self.host = f"[{self.host}]"
        self.username = username
        self.password = password
        self.gateway_type = None
        self.gateway_serial_num = gateway_serial_num
        self.use_token_auth = use_token_auth
        self.endpoint_results = {}
        self.meters_enabled = False
        self.get_inverters = inverters
        self._async_client = async_client
        self._cookies = None
        self._protocol = "https" if use_token_auth else "http"
        if self.use_token_auth:
            self._enphase_token = EnphaseToken(username, password)
        else:
            self._enphase_token = None

    @property
    def async_client(self):
        """Return async http client.
        
        Defaults to httpx async client.
        
        Returns
        -------
        async_client
            Async http client.
            
        """
        return self._async_client or httpx.AsyncClient(
            verify=False,
            timeout=10.0,
            headers=self._auth_header,
            cookies=self._cookies
        )

    @property
    def _auth_header(self):
        """Return authorization header if self._token is availiable."""
        if token := self._enphase_token.token:
            return {"Authorization": f"Bearer {token}"}
        else:
            return None

    async def getData(self, getInverters=True):
        """Fetch data from the endpoint.
        
        Parameters
        ----------
        getInverters : bool, optional
            Fetch single inverter data or not. The default is True.

        Returns
        -------
        None.

        """
        # Check if the Secure flag is set
        if self.use_token_auth:
            self._enphase_token.check()

        if not self.gateway_type:
            await self._setup_gateway()

        await self._update()

        if not self.get_inverters or not getInverters:
            return

        inverters_url = ENDPOINT_URL_PRODUCTION_INVERTERS.format(
            self._protocol, self.host
        )
        inverters_auth = httpx.DigestAuth(self.username, self.password)

        response = await self._async_get(
            inverters_url, auth=inverters_auth
        )
        _LOGGER.debug(
            "Fetched from %s: %s: %s",
            inverters_url,
            response,
            response.text,
        )
        if response.status_code == 401:
            response.raise_for_status()
        self.endpoint_results["production_inverters"] = response
        return

    async def _update(self, detection=False, gateway_type=None):
        """Fetch all endpoints for the given gateway_type.
        
        Fetch the endpoints and update the endpoint_results dict.
        The Gateway's endpoints are specified in the GATEWAY_ENDPOINTS dict.

        Parameters
        ----------
        detection : bool, optional
            If True update the endpoints mapped in GATEWAY_DETECTION_ENDPOINTS.
            The default is False.
        gateway_type : str, optional
            Type of gateway. The default is None.

        Returns
        -------
        None.

        """
        gateway_type = gateway_type if gateway_type else self.gateway_type
        if detection:
            endpoints = GATEWAY_DETECTION_ENDPOINTS[gateway_type]
        else:
            endpoints = GATEWAY_ENDPOINTS[gateway_type]
        for key, endpoint in endpoints.items():
            await self._update_endpoint(key, endpoint)
            # TODO: check if for loop is viable for async.
    
    async def _update_endpoint(self, key, url):
        """Fetch the given endpoint and update the endpoint_results dict."""
        formatted_url = url.format(self._protocol, self.host)
        response = await self._async_get(
            formatted_url, follow_redirects=False
        )
        self.endpoint_results[key] = response
    
    async def _async_get(self, url, handle_401=True, **kwargs):
        """Fetch endpoint and retry in case of a transport error.
        
        Parameters
        ----------
        url : str
            Endpoint url.
        handle_401 : bool, optional
            If True try to resolve 401 error. The default is False.
        **kwargs : dict, optional
            Extra arguments to httpx client.post()..

        Returns
        -------
        TYPE
            DESCRIPTION.

        """
        for attempt in range(1, 4):
            _LOGGER.debug(
                f"HTTP GET Attempt #{attempt}: {url}: Header:{self._auth_header}"
            )
            async with self.async_client as client:
                try:
                    r = await client.get(
                        url, headers=self._auth_header, **kwargs
                    )
                    r.raise_for_status()
                except httpx.HTTPStatusError as err:
                    status_code = err.response.status_code
                    _LOGGER.debug(
                        f"Received status_code {status_code} from Envoy."
                    )
                    if status_code == 401 and handle_401:
                        _LOGGER.debug("Trying to refresh token.")
                        try:
                            self._update_token()
                        except:
                            _LOGGER.debug("Error Trying to refresh token.")
                            raise err
                        else:
                            return(
                                self._async_get(url, handle_401=False, **kwargs)
                            )
                    elif status_code == 503:
                        raise RuntimeError(
                            "Envoy Service temporary unavailable (503)."
                        )
                    else:
                        raise
                except httpx.TransportError:
                    if attempt >= 3:
                        _LOGGER.debug(
                            f"Transport Error while trying HTTP GET: {url}"
                        )
                        raise
                    else:
                        await asyncio.sleep(attempt * 0.15)
                else:
                    _LOGGER.debug(f"Fetched from {url}: {r}: {r.text}")
                    return r    
    
    async def _async_post(self, url, retries=2, raise_for_status=True, **kwargs):
        """Post using async.
        
        Parameters
        ----------
        url : str
            HTTP POST target url.
        retries : int, optional
            Number of retries to perform after the initial post request fails. 
            The default is 2.
        raise_for_status : bool, optional
            If True raise an exception for non 2xx responses.
            The default is True.
        **kwargs : dict, optional
            Extra arguments to httpx client.post().

        Returns
        -------
        r : http response
            HTTP POST response object.

        """
        async with self.async_client as client:
            for attempt in range(1, retries+1):
                _LOGGER.debug(f"HTTP POST Attempt: #{attempt}: {url}")
                try:
                    r = await client.post(url, **kwargs)
                    if raise_for_status:
                        r.raise_for_status()
                    _LOGGER.debug(f"HTTP POST {url}: {r}: {r.text}")
                    _LOGGER.debug(f"HTTP POST Cookie: {r.cookies}")
                except httpx.HTTPStatusError as err:
                    status_code = err.response.status_code
                    _LOGGER.debug(
                        f"Received status_code {status_code} from Envoy."
                    )
                    if status_code == 503:
                        raise RuntimeError(
                            "Envoy Service temporary unavailable (503)"
                        )
                    else:
                        raise
                except httpx.TransportError:
                    if attempt >= retries + 1:
                        raise
                    else:
                        await asyncio.sleep(attempt * 0.15)
                else:
                    return r
        
    async def _setup_gateway(self):
        """Try to detect and setup the Enphase Gateway.
        
        Detection assumptions:
            Envoy Model S gateways can reach the 'production.json' endpoint.
            Envoy Model S Metered gateways have prodcution and comsumption keys.
            Envoy Model C gateways can reach the 'api/v1/production' endpoint.
            Envoy Legacy gateways can reach the 'production' endpoint
        
        Raises
        ------
        RuntimeError
            Raise if the production_json response has status_code: 401.

        Returns
        -------
        None.

        """
        # If a password was not given as an argument when instantiating
        # the EnvoyReader object than use the last six numbers of the serial
        # number as the password. Otherwise use the password argument value.
        if self.password == "" and not self.use_token_auth:
            self.password = await self._get_password_from_serial_num()
        
        try:
            self.endpoint_results = {}
            await self._update(detection=True, gateway_type="ENVOY_MODEL_S")
        except httpx.HTTPError:
            pass
        
        if production_json := self.endpoint_results.get("production_json"):
            status_code = production_json.status_code
            if status_code == 200:
                if has_production_and_consumption(production_json.json()):
                    self.meters_enabled = has_metering_setup(
                        production_json.json()
                    )
                    self.gateway_type = "ENVOY_MODEL_S_METERED"
                    self.endpoint_results = {}
                    return
                else:
                    self.gateway_type = "ENVOY_MODEL_S_STANDARD"
                    self.endpoint_results = {}
                    return
            elif status_code == 401:
                raise RuntimeError(
                    """Could not connect to Envoy model. 
                    Appears your Envoy is running firmware that requires 
                    secure communcation.
                    Please enter the needed Enlighten credentials during setup.
                    """
                )
    
        try:
            self.endpoint_results = {}
            await self._update(detection=True, gateway_type="ENVOY_MODEL_C")
        except httpx.HTTPError:
            pass
        
        if production_v1 := self.endpoint_results.get("production_v1"):
            if production_v1.status_code == 200:
                self.gateway_type = "ENVOY_MODEL_C"
                self.endpoint_results = {}
                return
    
        try:
            self.endpoint_results = {}
            await self._update(detection=True, gateway_type="ENVOY_MODEL_LEGACY")
        except httpx.HTTPError:
            pass
        
        if production := self.endpoint_results.get("production_legacy"):
            if production.status_code == 200:
                self.gateway_type = "ENVOY_MODEL_LEGACY"
                self.endpoint_results = {}
                return
        
        raise RuntimeError(
            "Could not connect or determine Envoy model. "
            + "Check that the device is up at 'http://"
            + self.host
            + "'."
        )

    async def _get_password_from_serial_num(self):
        """Generate gateway's password from serial number.
        
        Returns
        -------
        password
            Gateway password.

        """
        serial_num = self.gateway_serial_num or await self._get_serial_number()
        if serial_num:
            if self.username == "envoy" or self.username != "installer":
                return serial_num[-6:]
            else:
                return EnvoyUtils.get_password(serial_num, self.username)
        else:
            return None

    async def _get_serial_number(self):
        """Get the Envoy serial number."""
        response = await self._async_get(
            f"http{self._protocol}://{self.host}/info.xml",
            follow_redirects=True,
        )
        if not response.text:
            return None
        if "<sn>" in response.text:
            return response.text.split("<sn>")[1].split("</sn>")[0]
        match = SERIAL_REGEX.search(response.text)
        if match:
            return match.group(1)

    def create_connect_errormessage(self):
        """Create error message if unable to connect to Envoy."""
        return (
            "Unable to connect to Envoy. "
            + "Check that the device is up at 'http://"
            + self.host
            + "'."
        )

    def create_json_errormessage(self):
        """Create error message if unable to parse JSON response."""
        return (
            "Got a response from '"
            + self.host
            + "', but metric could not be found. "
            + "Maybe your model of Envoy doesn't "
            + "support the requested metric."
        )

    async def production(self):
        """Return the current power production value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.
        
        Raises
        ------
        RuntimeError
            Raise an Runtime Error if regex syntax is invalid.

        Returns
        -------
        int
            Current power production in W.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED":
            raw_json = self.endpoint_results["production_json"].json()
            idx = 1 if self.meters_enabled else 0
            production = raw_json["production"][idx]["wNow"]
            
        elif self.gateway_type == "ENVOY_MODEL_S_STANDARD":
            raw_json = self.endpoint_results["production_json"].json()
            production = raw_json["production"][0]["wNow"]
            
        elif self.gateway_type == "ENVOY_MODEL_C":
            raw_json = self.endpoint_results["production_v1"].json()
            production = raw_json["wattsNow"]
        
        elif self.gateway_type == "ENVOY_MODEL_LEGACY":
            text = self.endpoint_results["production_legacy"].text
            match = re.search(PRODUCTION_REGEX, text, re.MULTILINE)
            if match:
                if match.group(2) == "kW":
                    production = float(match.group(1)) * 1000
                else:
                    if match.group(2) == "mW":
                        production = float(match.group(1)) * 1000000
                    else:
                        production = float(match.group(1))
            else:
                raise RuntimeError("No match for production, check REGEX  " + text)
        return int(production)

    async def daily_production(self):
        """Return todays energy production value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.

        Raises
        ------
        RuntimeError
            Raise an Runtime Error if regex syntax is invalid.

        Returns
        -------
        int
            Todays energy production in Wh.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED":
            raw_json = self.endpoint_results["production_json"].json()
            if self.meters_enabled:
                daily_production = raw_json["production"][1]["whToday"]
            else:
                return self.messages["daily_production_not_available"]
        
        elif self.gateway_type in {"ENVOY_MODEL_S_STANDARD", "ENVOY_MODEL_C"}:
            raw_json = self.endpoint_results["production_v1"].json()
            daily_production = raw_json["wattHoursToday"]    
        
        elif self.gateway_type == "ENVOY_MODEL_LEGACY":
            text = self.endpoint_results["production_legacy"].text
            match = re.search(DAY_PRODUCTION_REGEX, text, re.MULTILINE)
            if match:
                if match.group(2) == "kWh":
                    daily_production = float(match.group(1)) * 1000
                else:
                    if match.group(2) == "MWh":
                        daily_production = float(match.group(1)) * 1000000
                    else:
                        daily_production = float(match.group(1))
            else:
                raise RuntimeError(
                    "No match for Day production, " "check REGEX  " + text
                )
        return int(daily_production)

    async def seven_days_production(self):
        """Return last seven days energy production value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.

        Raises
        ------
        RuntimeError
            Raise an Runtime Error if regex syntax is invalid.

        Returns
        -------
        int
            Last seven days energy production in Wh.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED":
            raw_json = self.endpoint_results["production_json"].json()
            if self.meters_enabled:
                seven_days_production = raw_json["production"][1]["whLastSevenDays"]
            else:
                return self.messages["seven_day_production_not_available"]
        
        elif self.gateway_type in {"ENVOY_MODEL_S_STANDARD", "ENVOY_MODEL_C"}:
            raw_json = self.endpoint_results["production_v1"].json()
            seven_days_production = raw_json["wattHoursSevenDays"]  
        
        elif self.gateway_type == "ENVOY_MODEL_LEGACY":
            text = self.endpoint_results["production_legacy"].text
            match = re.search(WEEK_PRODUCTION_REGEX, text, re.MULTILINE)
            if match:
                if match.group(2) == "kWh":
                    seven_days_production = float(match.group(1)) * 1000
                else:
                    if match.group(2) == "MWh":
                        seven_days_production = float(match.group(1)) * 1000000
                    else:
                        seven_days_production = float(match.group(1))
            else:
                raise RuntimeError(
                    "No match for 7 Day production, " "check REGEX " + text
                )    
        return int(seven_days_production)

    async def lifetime_production(self):
        """Return lifetime energy production value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.

        Raises
        ------
        RuntimeError
            Raise a Runtime Error if regex syntax is invalid.

        Returns
        -------
        int
            Lifetime energy production in Wh.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED":
            raw_json = self.endpoint_results["production_json"].json()
            idx = 1 if self.meters_enabled else 0
            lifetime_production = raw_json["production"][idx]["whLifetime"]
        
        elif self.gateway_type in {"ENVOY_MODEL_S_STANDARD", "ENVOY_MODEL_C"}:
            raw_json = self.endpoint_results["production_v1"].json()
            lifetime_production = raw_json["wattHoursLifetime"]  

        elif self.gateway_type == "ENVOY_MODEL_LEGACY":
            text = self.endpoint_results["production_legacy"].text
            match = re.search(LIFE_PRODUCTION_REGEX, text, re.MULTILINE)
            if match:
                if match.group(2) == "kWh":
                    lifetime_production = float(match.group(1)) * 1000
                else:
                    if match.group(2) == "MWh":
                        lifetime_production = float(match.group(1)) * 1000000
                    else:
                        lifetime_production = float(match.group(1))
            else:
                raise RuntimeError(
                    "No match for Lifetime production, " "check REGEX " + text
                ) 
        return int(lifetime_production)

    async def consumption(self):
        """Return current power consumption value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.
        
        Only return data if Envoy supports Consumption.

        Returns
        -------
        int or str
            Lifetime energy production in Wh if supported.
            If not supported an error message is returned.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED" and self.meters_enabled:
            raw_json = self.endpoint_results["production_json"].json()
            consumption = raw_json["consumption"][0]["wNow"]
        else:
            return self.messages["consumption_not_available"]
        return int(consumption)

    async def daily_consumption(self):
        """Return todays energy consumption value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.
        
        Only return data if Envoy supports Consumption.

        Returns
        -------
        int or str
            Todays energy consumption in Wh if supported.
            If not supported an error message is returned.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED" and self.meters_enabled:
            raw_json = self.endpoint_results["production_json"].json()
            daily_consumption = raw_json["consumption"][0]["whToday"]
        else:
            return self.messages["consumption_not_available"]
        return int(daily_consumption)

    async def seven_days_consumption(self):
        """Return last seven days energy consumption value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.
        
        Only return data if Envoy supports Consumption.

        Returns
        -------
        int or str
            Last seven days energy consumption in Wh if supported.
            If not supported an error message is returned.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED" and self.meters_enabled:
            raw_json = self.endpoint_results["production_json"].json()
            seven_days_consumption = raw_json["consumption"][0]["whLastSevenDays"]
        else:
            return self.messages["consumption_not_available"]
        return int(seven_days_consumption)

    async def lifetime_consumption(self):
        """Return lifetime energy consumption value.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.
        
        Only return data if Envoy supports Consumption.

        Returns
        -------
        int or str
            Lifetime energy consumption in Wh if supported.
            If not supported an error message is returned.

        """
        if self.gateway_type == "ENVOY_MODEL_S_METERED" and self.meters_enabled:
            raw_json = self.endpoint_results["production_json"].json()
            lifetime_consumption = raw_json["consumption"][0]["whLifetime"]
        else:
            return self.messages["consumption_not_available"]
        return int(lifetime_consumption)
        
    async def inverters_production(self):
        """Return inverters power production values.
        
        Running getData() beforehand will set self.enpoint_type 
        and self.isDataRetrieved so that this method will only read data 
        from stored variables.
        
        Only return data if Envoy supports retrieving Inverter data.

        Returns
        -------
        dict or None
            Dict containing inverter power production values in Wh if supported.
            If not supported None is returned.

        """
        if self.gateway_type == "ENVOY_MODEL_LEGACY":
            return None
        response_dict = {}
        try:
            for item in self.endpoint_results["production_inverters"].json():
                response_dict[item["serialNumber"]] = [
                    item["lastReportWatts"],
                    time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(item["lastReportDate"])
                    ),
                ]
        except (JSONDecodeError, KeyError, IndexError, TypeError, AttributeError):
            return None
        return response_dict

    async def battery_storage(self):
        """Return battery data from Envoys that support and have batteries installed."""
        if self.gateway_type in {"ENVOY_MODEL_C", "ENVOY_MODEL_LEGACY"}:
            return self.message_battery_not_available

        try:
            raw_json = self.endpoint_results["production_json"].json()
        except JSONDecodeError:
            return None

        """For Envoys that support batteries but do not have them installed the"""
        """percentFull will not be available in the JSON results. The API will"""
        """only return battery data if batteries are installed."""
        if "percentFull" not in raw_json["storage"][0].keys():
            # "ENCHARGE" batteries are part of the "ENSEMBLE" api instead
            # Check to see if it's there. Enphase has too much fun with these names
            if self.endpoint_results.get("ensemble_json") is not None:
                ensemble_json = self.endpoint_results["ensemble_json"].json()
                if len(ensemble_json) > 0 and "devices" in ensemble_json[0].keys():
                    return ensemble_json[0]["devices"]
            return self.messages["battery_not_available"]
        
        return raw_json["storage"][0]

    async def grid_status(self):
        """Return grid status reported by Envoy."""
        if self.endpoint_results.get("home_json") is not None:
            home_json = self.endpoint_results["home_json"].json()
            if "enpower" in home_json.keys() and "grid_status" in home_json["enpower"].keys():
                return home_json["enpower"]["grid_status"]
        
        return self.messages["grid_status_not_available"]


    def run_in_console(self):
        """If running this module directly, print all the values in the console."""
        print("Reading...")
        loop = asyncio.get_event_loop()
        data_results = loop.run_until_complete(
            asyncio.gather(self.getData(), return_exceptions=False)
        )

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(
            asyncio.gather(
                self.production(),
                self.consumption(),
                self.daily_production(),
                self.daily_consumption(),
                self.seven_days_production(),
                self.seven_days_consumption(),
                self.lifetime_production(),
                self.lifetime_consumption(),
                self.inverters_production(),
                self.battery_storage(),
                return_exceptions=False,
            )
        )

        print(f"production:              {results[0]}")
        print(f"consumption:             {results[1]}")
        print(f"daily_production:        {results[2]}")
        print(f"daily_consumption:       {results[3]}")
        print(f"seven_days_production:   {results[4]}")
        print(f"seven_days_consumption:  {results[5]}")
        print(f"lifetime_production:     {results[6]}")
        print(f"lifetime_consumption:    {results[7]}")
        if "401" in str(data_results):
            print(
                "inverters_production:    Unable to retrieve inverter data - Authentication failure"
            )
        elif results[8] is None:
            print(
                "inverters_production:    Inverter data not available for your Envoy device."
            )
        else:
            print(f"inverters_production:    {results[8]}")
        print(f"battery_storage:         {results[9]}")


if __name__ == "__main__":
    SECURE = ""

    parser = argparse.ArgumentParser(
        description="Retrieve energy information from the Enphase Envoy device."
    )
    parser.add_argument(
        "-u", "--user", dest="enlighten_user", help="Enlighten Username"
    )
    parser.add_argument(
        "-p", "--pass", dest="enlighten_pass", help="Enlighten Password"
    )
    parser.add_argument(
        "-c",
        "--comissioned",
        dest="commissioned",
        help="Commissioned Envoy (True/False)",
    )
    parser.add_argument(
        "-o",
        "--ownertoken",
        dest="ownertoken",
        help="use the 6 month owner token  from enlighten instead of the 1hr entrez token",
        action='store_true'
    )
    parser.add_argument(
        "-i",
        "--siteid",
        dest="enlighten_site_id",
        help="Enlighten Site ID. Only used when Commissioned=True.",
    )
    parser.add_argument(
        "-s",
        "--serialnum",
        dest="enlighten_serial_num",
        help="Enlighten Envoy Serial Number. Only used when Commissioned=True.",
    )
    args = parser.parse_args()

    if (
        args.enlighten_user is not None
        and args.enlighten_pass is not None
        and args.commissioned is not None
    ):
        SECURE = "s"

    HOST = input(
        "Enter the Envoy IP address or host name, "
        + "or press enter to use 'envoy' as default: "
    )

    USERNAME = input(
        "Enter the Username for Inverter data authentication, "
        + "or press enter to use 'envoy' as default: "
    )

    PASSWORD = input(
        "Enter the Password for Inverter data authentication, "
        + "or press enter to use the default password: "
    )

    if HOST == "":
        HOST = "envoy"

    if USERNAME == "":
        USERNAME = "envoy"

    if PASSWORD == "":
        TESTREADER = EnvoyReader(
            HOST,
            USERNAME,
            inverters=True,
            enlighten_user=args.enlighten_user,
            enlighten_pass=args.enlighten_pass,
            commissioned=args.commissioned,
            enlighten_site_id=args.enlighten_site_id,
            enlighten_serial_num=args.enlighten_serial_num,
            https_flag=SECURE,
            use_enlighten_owner_token=args.ownertoken
        )
    else:
        TESTREADER = EnvoyReader(
            HOST,
            USERNAME,
            PASSWORD,
            inverters=True,
            enlighten_user=args.enlighten_user,
            enlighten_pass=args.enlighten_pass,
            commissioned=args.commissioned,
            enlighten_site_id=args.enlighten_site_id,
            enlighten_serial_num=args.enlighten_serial_num,
            https_flag=SECURE,
            use_enlighten_owner_token=args.ownertoken
        )

    TESTREADER.run_in_console()
