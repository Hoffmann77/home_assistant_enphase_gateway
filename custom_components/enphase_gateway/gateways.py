"""Implements Enphase(R) Gateways"""


from .enphase_token import EnphaseToken


class BaseGateway:
    
    RUNTIME_ENDPOINTS = {}
    DETECTION_ENDPOINTS = {}

    def __init__(
            self,
            host,
            username,
            password="",
            serial_num=None,
            token_auth=False,
            cache_token=False,
            token_raw=None, # for future feature
            expose_token=False, # for future feature
            token_exposure_path=None, # for future feature
            get_inverters=False,
            store=None,
    ):
        """Init BaseGateway.

        Parameters
        ----------
        host : str
            DESCRIPTION.
        username : str
            Username for authentication.
        password : str, optional
            Password for authentication. The default is "".
        serial_num : TYPE, optional
            Gateway's serial number. The default is None.
        store : TYPE, optional
            DESCRIPTION. The default is None.


        Returns
        -------
        None.

        """
        self.host = host.lower()
        if is_ipv6_address(self.host):
            self.host = f"[{self.host}]"
        self.username = username
        self.password = password
        self.serial_num = serial_num
        self.endpoint_results = {}
        self.device_info = {}
        self.zeroconf_info = {}
        self.token_auth = token_auth
        self.store = store
        self._protocol = "https" if use_token_auth else "http"
        if self.token_auth:
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
        

    def _update(self, detection=False):
        
        endpoints = self._get_endpoints(detection)
        for key, endpoint in endpoints.items()
            formatted_url = url.format(self._protocol, self.host)
            response = await self._async_get(
                formatted_url,
                follow_redirects=False
            )
            self.endpoint_results[key] = response
        

    def _update_endpoint(self):
        pass

    def _get_endpoints(self, detection: bool=False) -> dict: #noqa
        """Return Endpoints dict.

        Parameters
        ----------
        detection : bool, optional
            If True return the detection endpoints.
            Otherwise return the runtime endpoints.
            The default is False.

        Returns
        -------
        dict
            Return the endpoints.

        """

        if detection:
            return self.DETECTION_ENDPOINTS
        else:
            return self.RUNTIME_ENDPOINTS

        
    
    
    
class EnvoyModelS(BaseGateway):
    
    DETECTION_ENDPOINTS = {
        "production_json": ENDPOINT_URL_PRODUCTION_JSON,
        "ensemble_inventory": ENDPOINT_URL_ENSEMBLE_INVENTORY
    }

    RUNTIME_ENDPOINTS = {
        "metered": {
            "production_json": ENDPOINT_URL_PRODUCTION_JSON,
            "home_json": ENDPOINT_URL_HOME_JSON,
        },
        "standard": {
            "production_v1": ENDPOINT_URL_PRODUCTION_V1,
            "home_json": ENDPOINT_URL_HOME_JSON,
        }
    }
    
    def __init__(
            self,
            meters_enabled,
    ):
        
        self.meters_enabled = meters_enabled
        
    @classmethod
    async def setup_gateway(self):
        pass

    def _get_endpoints(self, detection: bool=False) -> dict: #noqa
        """Return Endpoints dict.

        Parameters
        ----------
        detection : bool, optional
            If True return the detection endpoints.
            Otherwise return the runtime endpoints.
            The default is False.

        Returns
        -------
        dict
            Return the endpoints.

        """
        if detection:
            return self.DETECTION_ENDPOINTS
        else:
            key = "metered" if self.meters_enabled else "standard"
            return self.RUNTIME_ENDPOINTS[key]
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
