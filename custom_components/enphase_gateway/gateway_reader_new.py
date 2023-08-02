"""Module to read parameters from an Enphase gateway on the local network."""

import argparse
import asyncio
import logging
import re
import time
from json.decoder import JSONDecodeError
from typing import Iterable

import httpx
from envoy_utils.envoy_utils import EnvoyUtils
from homeassistant.util.network import is_ipv6_address

from ..http import async_get
from ..enphase_token import EnphaseToken
from .util.endpoint import Endpoint, ENDPOINT_URL_INFO_XML


_LOGGER = logging.getLogger(__name__)

SERIAL_REGEX = re.compile(r"Envoy\s*Serial\s*Number:\s*([0-9]+)")

GATEWAY_DETECTION_ENDPOINTS = {
    "ENVOY_MODEL_S": (
        Endpoint("production_json"),
        Endpoint("ensemble_inventory"),
    ),
    "ENVOY_MODEL_C": (
        Endpoint("production_v1"),
    ),
    "ENVOY_MODEL_LEGACY": (
        Endpoint("production_legacy"),
    )
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
            cache_token=False,
            expose_token=False, # for future feature
            token_exposure_path=None, # for future feature
            get_inverters=False,
            async_client=None,
            store=None,
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
        self.storages = {}
        self.gateway = None
        self.get_inverters = get_inverters
        self._async_client = async_client
        self._protocol = "https" if use_token_auth else "http"
        if self.use_token_auth:
            self._enphase_token = EnphaseToken(
                self.host,
                username,
                password,
                gateway_serial_num,
                token_raw=token_raw,
                token_store=store,
                cache_token=cache_token,
                expose_token=expose_token,
                exposure_path=token_exposure_path,
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
        """Return the authorization header."""
        if self._enphase_token:
            if token_raw := self._enphase_token.token:
                return {"Authorization": f"Bearer {token_raw}"}
            else:
                return None
        else:
            return None
        
    @property
    def _cookies(self):
        """Return the cookies from enphase_token."""
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
        
        if self.use_token_auth:
            await self._enphase_token.prepare()

        if not self.gateway_type:
            await self._setup_gateway()

        await self.update_endpoints()

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
    
    async def update_endpoints(self, endpoints=None, detection=False):
        """Update endpoints.
        
        Endpoints can be specified using the endpoints keyword argument.
        If no endpoints are provided, the endpoints will be determined based
        on the Gateway class.
        
        Parameters
        ----------
        endpoints : Iterable[Endpoint], optional
            Endpoints to update. The default is None.
        detection : bool, optional
            If True the response is stored in the endpoint_results dict.
            This is used to access the data for gateway detection.
            The default is False.

        Returns
        -------
        None.

        """
        if not endpoints:
            endpoints = self.gateway.required_endpoints
            
        for endpoint in endpoints:
            if endpoint.update_required:
                await self._update_endpoint(endpoint, detection)
                endpoint.updated()
 
    async def _update_endpoint(self, endpoint: Endpoint, detection: bool = False):
        """Fetch a single endpoint and store the response.
        
        Parameters
        ----------
        endpoint : Endpoint
            Endpoint to fetch.
        detection : bool, optional
            If True the response is stored in the endpoint_results dict.
            This is used to access the data for gateway detection.
            The default is False.

        Returns
        -------
        None.

        """
        formatted_url = endpoint.url.format(self._protocol, self.host)
        response = await self._async_get(
            formatted_url,
            follow_redirects=False
        )
        if detection:
            self.endpoint_results[endpoint.name] = response
        elif self.gateway:
            self.gateway.set_endpoint_data(endpoint, response)
        
    async def _async_get(self, url: str, handle_401: bool = True, **kwargs):
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
        
        for gateway_type, endpoints in GATEWAY_DETECTION_ENDPOINTS.items():
            self.endpoint_results = {}
            try:
                await self.update_endpoints(
                    endpoints=endpoints,
                    detection=True,
                ) 
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
                try:
                    production_json = production_json.json()
                except JSONDecodeError:
                    _LOGGER.debug("JSON Decode error: '_setup_envoy_model_s'")
                    return False
                else:
                    if has_production_and_consumption(production_json):
                        self.meters_enabled = has_metering_setup(
                            production_json
                        )
                        self.gateway_type = "ENVOY_MODEL_S_METERED"
                    else:
                        self.gateway_type = "ENVOY_MODEL_S_STANDARD"
        
        if self.gateway_type:
            if "percentFull" in production_json["storage"][0].keys():
                self.storages.update({"acb": True})
            
            if inventory := self.endpoint_results.get("ensemble_inventory"):
                try:
                    ensemble_inventory = inventory.json()
                except JSONDecodeError:
                    _LOGGER.debug("JSON Decode error: '_setup_envoy_model_s'")
                    pass
                else:
                    for entry in ensemble_inventory:
                        storage_type = entry.get("type")
                        if "devices" in entry.keys():
                            self.storages.update({storage_type: True})
            
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
                self.get_inverters = False
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
    
    async def gateway_info(self):
        """Return information about the devices."""
        if self.gateway_type:
            strings = self.gateway_type.lower().split("_")
            gateway_type = " ".join(string.capitalize() for string in strings)
        return {
            "gateway_type": gateway_type or None
        }
        


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

