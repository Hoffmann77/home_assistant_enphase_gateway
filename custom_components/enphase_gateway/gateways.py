"""Implements Enphase(R) Gateways"""

import time
import logging
import xmltodict
from datetime import datetime, timezone

from jsonpath import jsonpath
from jsonpath2.path import Path as JsonPath
from httpx import Response

from .enphase_token import EnphaseToken
from .gateway_reader import GatewayReader

_LOGGER = logging.getLogger(__name__)


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
    "production": ENDPOINT_URL_PRODUCTION,
    "production_v1": ENDPOINT_URL_PRODUCTION_V1,
    "production_json": ENDPOINT_URL_PRODUCTION_JSON,
    "production_inverters": ENDPOINT_URL_PRODUCTION_INVERTERS,
    "ensemble_inventory": ENDPOINT_URL_ENSEMBLE_INVENTORY,
    "ensemble_power": ENDPOINT_URL_ENSEMBLE_POWER,
}


def is_property(property_instance):
    """Check if the given property is a property instance."""
    return isinstance(property_instance, (JsonPathProperty))
        

def get_endpoint_url(endpoint_uid):
    """Return the url for a endpoint."""
    return ENDPOINTS.get(endpoint_uid)
    
    
def gateway_property(_func=None, **kwargs):
    """Register method as property.
    
    Parameters
    ----------
    _func : Method, optional
        Instance of Method. The default is None.
    **kwargs : dict
        Optional keyword arguments.

    Returns
    -------
    property
        Return a property attribute.

    """
    endpoint = kwargs.pop("required_endpoint", None)
    cache = kwargs.pop("cache", 0)

    def decorator(func):
        
        # Can be used for function calls
        # def inner(self, *args, **kwargs):
        #     type(self)._envoy_properties[func.__name__] = endpoint
        #     return func(self, *args, **kwargs)
        # return inner
        
        _endpoint = (endpoint, cache) if endpoint else None
        BaseGateway._properties[func.__name__] = _endpoint
        return property(func)
    
    if _func == None:
        return decorator
    else:
        return decorator(_func)
    
    
class Endpoint:
    """Class representing a Gateway endpoint."""
    
    def __init__(self, name, cache=0):
        self.name = name
        self.url = ENDPOINTS.get(name)
        self.cache = cache
        self.last_fetch = None
    
    def __repr__(self):
        return self.name
    
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
        

class JsonPathProperty:
    """JasonPath Gateway property."""
    
    def __init__(self, jsonpath_expr: str, cache: int | None = None):
        """Initialize instance of JsonPathProperty.
        
        Parameters
        ----------
        jsonpath_expr : str 
            JsonPath expression.
        cache : int or None, optional
            Number of seconds to cache endpoint. The default is None.

        Returns
        -------
        None.

        """
        self.jsonpath_expr = jsonpath_expr
        self.cache = cache
    
    def __get__(self, obj, objtype=None):
        """Magic method."""
        return self.resolve(obj.data)
       
    @property
    def required_endpoint(self) -> tuple:
        """Return the reqired endpoint.
        
        Returns
        -------
        tuple
            Required endpoint.

        """
        return (self.jsonpath_expr.split(".", 1)[0], self.cache) 
  
    def resolve(self, data, default=None):
        """Resolve the JsonPath and return the value.
        
        Parameters
        ----------
        data : dict
            Dict containing endpoint data.
        default : TYPE
            Default value if the result is empty.

        Returns
        -------
        result
            Return the result from the resolved jsonpath.
            Returns default if the result is empty.

        """
        _LOGGER.debug("Resolving jsonpath {self.path}")
        result = jsonpath(data, self.jasonpath_expr)
        
        if result == False:
            _LOGGER.debug(
                "the configured path {self.path} did not return anything!"
            )
            return default

        if isinstance(result, list) and len(result) == 1:
            result = result[0]

        return result
        
    


class BaseGateway:
    """Parent Gateway class providing getter and setter methods for data."""

    _properties = {}

    def __new__(cls, *args, **kwargs):
        """Magic method."""
        cls._attributes = []
        for attr in dir(cls):
            if is_property(getattr(cls, attr)):
                cls._attributes.append(attr)

            elif isinstance(getattr(cls, attr), property):
                if attr in cls._properties:
                    cls._attributes.append(attr)

        return object.__new__(cls)

    def __init__(self, gateway_reader: GatewayReader):
        """Initialize instance of BaseGateway.
        
        Parameters
        ----------
        gateway_reader : GatewayReader
            Instance of GatewayReader.

        Returns
        -------
        None.

        """
        self.reader = gateway_reader
        self.data = {}
        self.initial_update_finished = False
        self._required_endpoints = None # cache required endpoints

    def set_endpoint_data(self, endpoint: Endpoint, response: Response):
        """Set data for endpoint.

        Parameters
        ----------
        endpoint_id : str
            Endpoint ID.
        response : http Response
            HTTP response object.

        Returns
        -------
        None.

        """
        # if response.status_code > 400:
        #     # It is a server error, do not store endpoint_data
        #     return

        content_type = response.headers.get("content-type", "application/json")
        if content_type == "application/json":
            self.data[endpoint] = response.json()
        elif content_type in ("text/xml", "application/xml"):
            self.data[endpoint] = xmltodict.parse(response.text)
        else:
            self.data[endpoint] = response.text

    @property
    def required_endpoints(self) -> list[Endpoint]:
        """Return all the required endpoints for this Gateway.
        
        Returns
        -------
        endpoints : dict
            Set of all required endpoints.

        """
        if self._required_endpoints:
            return self._required_endpoints

        _endpoints = {}
        
        def update_endpoints(endpoint):
            _endpoint = _endpoints.get(endpoint[0], None)
            if not _endpoint or _endpoint < endpoint[1]:
                _endpoints[endpoint[0]] = endpoint[1]
            
        # Loop through all local attributes, and return unique first required jsonpath attribute.
        for attr in dir(self):
            if is_property(prop := getattr(self, attr)):
                if self.initial_update_finished:
                    # Check if the path resolves, if not, do not include endpoint.
                    if self._resolve_property(prop) is None:
                        # If the resolved path is None, 
                        # we skip this path for the endpoints.
                        continue
                
                update_endpoints(prop.required_endpoint)
                continue  # discovered, so continue

            if attr in self._properties and isinstance(
                self._properties[attr], tuple
            ):
                value = getattr(self, attr)
                if self.initial_update_finished and value in (None, [], {}):
                    # When the value is None or empty list or dict,
                    # then the endpoint is useless for this token,
                    # so do not require it.
                    continue
                
                update_endpoints(self._properties[attr])
                continue  # discovered, so continue
        
        endpoints = []
        for endpoint, cache in _endpoints.items():
            endpoints.append(Endpoint(endpoint, cache=cache))
            
        if self.initial_update_finished:
            # Save the list in memory, as we should not evaluate this list again.
            # If the list needs re-evaluation, then reload the plugin.
            self._required_endpoints = endpoints

        return endpoints

    @property
    def all_values(self) -> dict[str, int | float]:
        """Return a dict containing all attributes.
        
        Returns
        -------
        dict
            Dict containing all attributes with their value.

        """
        result = {}
        for attr in self._attributes:
            result[attr] = getattr(self, attr)

        return result

    def _resolve_property(self, gateway_property, default=None):
        """Resolve the given gateway_property."""
        return gateway_property.resolve(self.data, default)
  
    def _resolve_path(self, path, default=None):
        _LOGGER.debug("Resolving jsonpath %s", path)

        result = jsonpath(self.data, path)
        if result == False:
            _LOGGER.debug("the configured path %s did not return anything!", path)
            return default

        if isinstance(result, list) and len(result) == 1:
            result = result[0]

        return result

    def _path_to_dict(self, paths, keyfield):
        if not isinstance(paths, list):
            paths = [paths]

        new_dict = {}
        for path in paths:
            for d in self._resolve_path(path, default=[]):
                key = d.get(keyfield)
                new_dict.setdefault(key, d).update(**d)

        return new_dict

    def __getattr__(self, name):
        """
        This magic function will be called for all attributes that have not been defined explicitly
        It will look for <variable>_value attribute, that should hold the json path to be searched
        for in self.data
        self.data is populated whenever EnvoyReader.update_endpoints has a successfull url download
        """
        result = None
        if (attr := f"{name}_value") in dir(self):
            path = getattr(self, attr)
            result = self._resolve_path(path)
        elif name in self._envoy_properties:
            result = getattr(self, name)
        else:
            _LOGGER.warning("Attribute %s unknown", name)

        _LOGGER.debug(f"EnvoyData.get({name}) -> {result}")
        return result

    get = __getattr__






class EnvoyS(BaseGateway):
    """Enphase(R) Envoy Model S Standard Gateway."""
    
    production = JsonPathProperty("production_v1.wattsNow")
    
    daily_production = JsonPathProperty("production_v1.wattHoursToday")
    
    seven_days_production = JsonPathProperty("production_v1.whLastSevenDays")
    
    lifetime_production = JsonPathProperty("production_v1.wattHoursLifetime")
    
    @gateway_property(required_endpoint="production_inverters")
    def inverters_production(self):
        """Inverters production value."""
        data = self.data.get("production_inverters")
        def iter():
            for item in data:
                yield item["serialNumber"], {
                    "watt": item["lastReportWatts"],
                    "report_data": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(
                            item["lastReportDate"]
                        )
                    ),
                }
        return dict(iter())
    




def select_by_production_ct(enabled, disabled):
    def prop(cls):
        if cls.production_ct:
            return enabled
        return disabled
    
    return property(prop)

    
    

class EnvoySMetered(EnvoyS):
    """Enphase(R) Envoy Model S Metered Gateway."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.production_ct = kwargs.get("production_ct", True)
        self.consumption_ct = kwargs.get("consumption_ct", True)
        
    _production = select_by_production_ct(
        "production_json.production[?(@.type=='eim' && @.activeCount > 0)]",
        "production_json.production[?(@.type=='inverters')]"
    )
    
    _total_consumption = (
        """production_json.consumption[?(@.measurementType == 
        'total-consumption' && @.activeCount > 0)]"""
    )
    
    production = JsonPathProperty(_production + ".wNow")
    
    lifetime_production = JsonPathProperty(_production + ".whLifetime")
    
    @property
    def daily_production(self):
        """Todays energy production."""
        if self.production_ct:
            return JsonPathProperty(self._production + ".whToday")
        else:
            return None
     
    @property
    def seven_days_production(self):
        """Last seven days energy production."""
        if self.production_ct:
            return JsonPathProperty(self._production + ".whLastSevenDays")
        else:
            return None
    
    @property
    def consumption(self):
        """Todays energy production."""
        if self.consumption_ct:
            return JsonPathProperty(self._total_consumption + ".wNow")
        else:
            return None

    @property
    def daily_consumption(self):
        """Todays energy production."""
        if self.consumption_ct:
            return JsonPathProperty(self._total_consumption + ".whToday")
        else:
            return None
        
    @property
    def seven_days_consumption(self):
        """Todays energy production."""
        if self.consumption_ct:
            return JsonPathProperty(self._total_consumption + ".whLastSevenDays")
        else:
            return None
        
    @property
    def lifetime_consumption(self):
        """Todays energy production."""
        if self.consumption_ct:
            return JsonPathProperty(self._total_consumption + ".whLifetime")
        else:
            return None
    



    
    
 
