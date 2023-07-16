"""Module to read energy related parameters from an Enphase gateway on the local network."""

import argparse
import asyncio
import logging
import re
import time
from json.decoder import JSONDecodeError

import httpx
from envoy_utils.envoy_utils import EnvoyUtils
from homeassistant.util.network import is_ipv6_address

from ..http import async_get
from ..enphase_token import EnphaseToken


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
ENDPOINT_URL_ENSEMBLE_POWER = "{}://{}/ivp/ensemble/power"
ENDPOINT_URL_HOME_JSON = "{}://{}/home.json"
ENDPOINT_URL_INFO_XML = "{}://{}/info.xml"

_LOGGER = logging.getLogger(__name__)

# Endpoints used to fetch data.
GATEWAY_ENDPOINTS = {
    'ENVOY_MODEL_S_METERED': {
        "production_json": ENDPOINT_URL_PRODUCTION_JSON,
        "home_json": ENDPOINT_URL_HOME_JSON,
    },
    'ENVOY_MODEL_S_STANDARD': {
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

# Endpoints for storage data
ENSEMBLE_ENDPOINTS = {
    "ensemble_inventory": ENDPOINT_URL_ENSEMBLE_INVENTORY,
    "ensemble_power": ENDPOINT_URL_ENSEMBLE_POWER,
}

# Endpoints used to detect the type of gateway.
GATEWAY_DETECTION_ENDPOINTS = {
    "ENVOY_MODEL_S": {
        "production_json": ENDPOINT_URL_PRODUCTION_JSON,
        "ensemble_inventory": ENDPOINT_URL_ENSEMBLE_INVENTORY,
    },
    "ENVOY_MODEL_C": {
        "production_v1": ENDPOINT_URL_PRODUCTION_V1,
    },
    "ENVOY_MODEL_LEGACY": {
        "production": ENDPOINT_URL_PRODUCTION,
    }
}


def has_production_and_consumption(_json):
    """Check if json has keys for both production and consumption."""
    return "production" in _json and "consumption" in _json


def has_metering_setup(_json):
    """Check if Active Count of Production CTs (eim) installed is greater than one."""
    return True if _json["production"][1]["activeCount"] > 0 else False


class SwitchToHTTPS(Exception):
    """Switch to https exception."""
    
    pass


class GatewayReader:
    """Instance of EnvoyReader."""

    MESSAGES = {
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
            token_raw=None,
            use_token_cache=False,
            token_cache_filepath=None,
            single_inverter_entities=False,
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
        self.device_info = {}
        self.fetch_ensemble = False
        self.get_inverters = inverters
        self._async_client = async_client
        self._protocol = "https" if use_token_auth else "http"
        if self.use_token_auth:
            self._enphase_token = EnphaseToken(
                self.host,
                username,
                password,
                gateway_serial_num,
                token_raw=token_raw,
                use_token_cache=use_token_cache,
                token_cache_filepath=token_cache_filepath,
            )
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
        """Return authorization header."""
        if self._enphase_token:
            if token_raw := self._enphase_token.token:
                return {"Authorization": f"Bearer {token_raw}"}
            else:
                return None
        else:
            return None
        
    @property
    def _cookies(self):
        """Return cookies from enphase_token."""
        if self._enphase_token:
            return self._enphase_token.cookies or None
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
        # TODO check that token is valid. No token race condition
        
        # Check if the Secure flag is set
        if self.use_token_auth:
            await self._enphase_token.prepare()

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
            if self.fetch_ensemble:
                endpoints.update(ENSEMBLE_ENDPOINTS)
        for key, endpoint in endpoints.items():
            await self._update_endpoint(key, endpoint, detection)
            # TODO: check if for loop is viable for async.
    
    async def _update_endpoint(self, key, url, detection):
        """Fetch the given endpoint and update the endpoint_results dict."""
        formatted_url = url.format(self._protocol, self.host)
        response = await self._async_get(
            formatted_url,
            follow_redirects=False
        )
        self.endpoint_results[key] = response
    
    async def _async_get(self, url, handle_401=True, **kwargs):
        """Send a HTTP GET request.

        Parameters
        ----------
        url : str
            Target url.
        handle_401 : bool, optional
            Try to resolve 401 errors if True. The default is True.
        **kwargs : dict, optional
            Extra arguments to httpx client.post().

        Raises
        ------
        err : httpx.HTTPStatusError
         HTTP status error.

        Returns
        -------
        resp : httpx.Response
            HTTP response.

        """
        try:
            resp = await async_get(
                url,
                self.async_client,
                headers=self._auth_header,
                cookies=self._cookies,
                **kwargs
            )

        except httpx.HTTPStatusError as err:
            status_code = err.response.status_code
            _LOGGER.debug(
                f"Received status_code {status_code} from Gateway"
            )
            if status_code == 401 and handle_401 and self.use_token_auth:
                _LOGGER.debug(
                    "Trying to resolve 401 error - Refreshing cookies"
                )
                if not await self._enphase_token.refresh_cookies():
                    _LOGGER.debug("Refreshing Enphase token")
                    try:
                        await self._enphase_token.refresh()
                    except Exception as exc:
                        _LOGGER.debug(
                            f"Error while refreshing token: {exc}"
                        )
                        _LOGGER.debug("Raising initial 401 error")
                        raise err
                        
                return await self._async_get(url, handle_401=False, **kwargs)
                    
            else:
                raise err

        else:
            return resp

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
        _LOGGER.debug("Trying to detect Enphase gateway")
        # If a password was not given as an argument when instantiating
        # the EnvoyReader object than use the last six numbers of the serial
        # number as the password. Otherwise use the password argument value.
        if self.password == "" and not self.use_token_auth:
            self.password = await self._get_password_from_serial_num()
        
        for gateway_type in GATEWAY_DETECTION_ENDPOINTS.keys():    
            self.endpoint_results = {}
            try:
                await self._update(detection=True, gateway_type=gateway_type) 
            except httpx.HTTPStatusError as err:
                status_code = err.response.status_code
                if status_code == 401 and self.use_token_auth:
                    raise err
            except httpx.HTTPError:
                pass
            
            func_name = f"_setup_{gateway_type.lower()}"
            if setup_function := getattr(self, func_name, None):
                if await setup_function():
                    self.endpoint_results = {}
                    return
                else:
                    continue
            else:
                raise RuntimeError("Missing setup function: {gateway_type}")
        
        raise RuntimeError(f"""
            Could not connect or determine Envoy model. 
            Check that the device is up at 'http://{self.host}'."""
        )
    
    async def _setup_envoy_model_s(self):
        if production_json := self.endpoint_results.get("production_json"):
            status_code = production_json.status_code
            if status_code == 200:
                if has_production_and_consumption(production_json.json()):
                    self.meters_enabled = has_metering_setup(
                        production_json.json()
                    )
                    self.gateway_type = "ENVOY_MODEL_S_METERED"
                else:
                    self.gateway_type = "ENVOY_MODEL_S_STANDARD"
        
        if self.gateway_type:
            if inventory := self.endpoint_results.get("ensemble_inventory"):
                inventory = inventory.json()
                if len(inventory) > 0 and "devices" in inventory[0].keys():
                    self.fetch_ensemble = True     
            return True
        
        return False
    
    async def _setup_envoy_model_c(self):
        if production_v1 := self.endpoint_results.get("production_v1"):
            if production_v1.status_code == 200:
                self.gateway_type = "ENVOY_MODEL_C"
                return True
        return False
    
    async def _setup_envoy_model_legacy(self):
        if production := self.endpoint_results.get("production_legacy"):
            if production.status_code == 200:
                self.gateway_type = "ENVOY_MODEL_LEGACY"
                return True
        return False
    
    async def _get_password_from_serial_num(self):
        """Generate gateway's password from serial number.
        
        Returns
        -------
        password
            Gateway password.

        """
        serial_num = self.gateway_serial_num or await self.get_serial_number()
        if serial_num:
            if self.username == "envoy" or self.username != "installer":
                return serial_num[-6:]
            else:
                return EnvoyUtils.get_password(serial_num, self.username)
        else:
            return None

    async def get_serial_number(self):
        """Try to fetch the serial number from /info.xml."""
        url = ENDPOINT_URL_INFO_XML.format(self._protocol, self.host)
        try:
            response = await self._async_get(url, follow_redirects=True).text
        except:
            return None
        else:
            if "<sn>" in response:
                return response.split("<sn>")[1].split("</sn>")[0]  
            elif match := SERIAL_REGEX.search(response):
                return match.group(1)
        
        return None
        
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
                return self.MESSAGES["daily_production_not_available"]
        
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
                return self.MESSAGES["seven_day_production_not_available"]
        
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
            return self.MESSAGES["consumption_not_available"]
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
            return self.MESSAGES["consumption_not_available"]
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
            return self.MESSAGES["consumption_not_available"]
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
            return self.MESSAGES["consumption_not_available"]
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
        """Return battery storages for supported gateways.
        
        For Envoys that support batteries but do not have an Enphase AC battery
        installed the 'percentFull' key will not be availiable in the
        production_json result.
        
        For Envoys that have an Encharge storage installed the ensemble 
        endpoints can be used to fetch battery data.
        

        Returns
        -------
        dict
            Battery dict.

        """
        if self.gateway_type in {"ENVOY_MODEL_C", "ENVOY_MODEL_LEGACY"}:
            return self.MESSAGES["battery_not_available"]

        try:
            production_json = self.endpoint_results["production_json"].json()
        except JSONDecodeError:
            return None
        
        if "percentFull" in production_json["storage"][0].keys():
            storage_json = production_json["storage"][0]
            return {"acb": storage_json}
            
        elif _inventory := self.endpoint_results.get("ensemble_inventory"):
            ensemble_inventory = _inventory.json()
            storages = {}
            for entry in ensemble_inventory:
                storage_type = entry.get("type")
                devices = entry.get("devices")
                storages.update({storage_type: devices})
                if devices and storage_type == "ENCHARGE":
                    storages.update(
                        {storage_type: {
                            item["serial_num"]: item for item in devices
                            }
                        }
                    )
            if storages:
                return storages
              
        return self.MESSAGES["battery_not_available"]  
    
    async def ensemble_power(self):
        """Return Encharge battery power values."""
        if ensemble_power := self.endpoint_results.get("ensemble_power"):
            ensemble_power = ensemble_power.json()
            return {
                item["serial_num"]: item for item in ensemble_power["devices:"]
            }
        return None
        
    async def grid_status(self):
        """Return grid status reported by Envoy."""
        if self.endpoint_results.get("home_json") is not None:
            home_json = self.endpoint_results["home_json"].json()
            if "enpower" in home_json.keys() and "grid_status" in home_json["enpower"].keys():
                return home_json["enpower"]["grid_status"]
        
        return self.MESSAGES["grid_status_not_available"]

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
    
    TESTREADER = GatewayReader(
        "192.168.178.",
        username="envoy",
        password="",
        gateway_serial_num=None,
        use_token_auth=False,
        token_raw=None,
        use_token_cache=False,
        token_cache_filepath=None,
        single_inverter_entities=False,
        inverters=False,
        async_client=None,
    )
        
    TESTREADER.run_in_console()

