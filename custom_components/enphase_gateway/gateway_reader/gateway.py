"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import time
import logging
import xmltodict
from typing import TYPE_CHECKING, Callable

from httpx import Response

from .const import AVAILABLE_PROPERTIES
from .endpoint import GatewayEndpoint
from .descriptors import JsonDescriptor, RegexDescriptor

from .models.ac_battery import ACBattery

if TYPE_CHECKING:
    from .gateway_reader import GatewayReader


_LOGGER = logging.getLogger(__name__)


def gateway_property(_func: Callable | None = None, **kwargs) -> property:
    """Gateway property decorator.
    
    Register the decorated method and it's required endpoint to 
    BaseGateway._gateway_properties.
    
    Return a property of the the decorated method.
    
    Parameters
    ----------
    _func : Callable, optional
        Decorated method. The default is None.
    **kwargs
        Optional keyword arguments.

    Returns
    -------
    property
        Property of the decorated method.

    """
    required_endpoint = kwargs.pop("required_endpoint", None)
    cache = kwargs.pop("cache", 0)

    def decorator(func):
        if required_endpoint:
            _endpoint = GatewayEndpoint(required_endpoint, cache)
        else:
            _endpoint = None
        
        BaseGateway._gateway_properties[func.__name__] = _endpoint
        return property(func)
    
    if _func == None:
        return decorator
    else:
        return decorator(_func)
    

def gateway_probe(_func: Callable | None = None, **kwargs) -> property:
    """Gateway probe decorator.
    
    Register the decorated method and it's required endpoint to 
    BaseGateway._gateway_probes.
    
    Return a property of the the decorated method.
    
    Parameters
    ----------
    _func : Callable, optional
        Decorated method. The default is None.
    **kwargs
        Optional keyword arguments.

    Returns
    -------
    property
        Property of the decorated method.

    """
    required_endpoint = kwargs.pop("required_endpoint", None)
    cache = kwargs.pop("cache", 0)

    def decorator(func):
        def inner(self, *args, **kwargs):
            if required_endpoint:
                _endpoint = GatewayEndpoint(required_endpoint, cache)
            else:
                _endpoint = None
            
            type(self)._gateway_probes[func.__name__] = _endpoint
            return func(self, *args, **kwargs)
        
        return inner
    
    if _func == None:
        return decorator
    else:
        return decorator(_func)
    
    
class BaseGateway:
    """Class providing getter and setter methods for data."""

    VERBOSE_NAME = "Enphase Gateway"

    _gateway_properties = {}
    _gateway_probes = {}
    
    def __init__(self) -> None:
        """Initialize BaseGateway."""
        self.data = {}
        self.initial_update_finished = False
        self._required_endpoints = None
    
    @property
    def all_values(self) -> dict[str, int | float]:
        """Return a dict containing all attributes.
        
        Returns
        -------
        dict
            Dict containing all attributes with their value.

        """
        result = {}
        for attr in self._gateway_properties.keys():
            result[attr] = getattr(self, attr)

        return result
    
    @property
    def required_endpoints(self) -> list[GatewayEndpoint]:
        """Return all required endpoints for this Gateway.
        
        Returns
        -------
        endpoints : list[GatewayEndpoint]
            List containing all required endpoints.

        """
        if self._required_endpoints:
            return self._required_endpoints

        endpoints = {}

        def update_endpoints(endpoint):
            _endpoint = endpoints.get(endpoint.name)
            
            if _endpoint == None:
                endpoints[endpoint.name] = endpoint
                
            elif endpoint.cache < _endpoint.cache:
                _endpoint.cache = endpoint.cache
        
        for prop, prop_endpoint in self._gateway_properties.items():
            if isinstance(prop_endpoint, GatewayEndpoint):
                
                value = getattr(self, prop)
                if self.initial_update_finished and value in (None, [], {}):
                    # When the value is None or empty list or dict,
                    # then the endpoint is useless for this token,
                    # so do not require it.
                    continue
                
                update_endpoints(prop_endpoint)
                
        if self.initial_update_finished:
            # Save the list in memory, as we should not evaluate this list again.
            # If the list needs re-evaluation, then reload the plugin.
            self._required_endpoints = endpoints        
        
        else:
            for probe, probe_endpoint in self._gateway_probes.items():
                if isinstance(probe_endpoint, GatewayEndpoint):
                    update_endpoints(probe_endpoint)
                
        return endpoints

    def set_endpoint_data(
            self, 
            endpoint: GatewayEndpoint,
            response: Response
    ) -> None:
        """Store the http Response of a specific endpoint.

        Parameters
        ----------
        endpoint : GatewayEndpoint
            Instance of GatewayEndpoint.
        response : httpx.Response
            HTTP response object.

        Returns
        -------
        None.

        """
        if response.status_code >= 400:
            return

        content_type = response.headers.get("content-type", "application/json")
        if content_type == "application/json":
            self.data[endpoint.name] = response.json()
        elif content_type in ("text/xml", "application/xml"):
            self.data[endpoint.name] = xmltodict.parse(response.text)
        elif content_type == "text/html":
            self.data[endpoint.name] = response.text
        else:
            self.data[endpoint.name] = response.text

    def probe(self):
        """Probe all probes."""
        for probe in self._gateway_probes.keys():
            func = getattr(self, probe)
            func()

    def __getattribute__(self, name):
        """Return None if gateway does not support this property."""
        if name in AVAILABLE_PROPERTIES:
            return None
        else:
            object.__getattribute__(self, name)
        
    def get(self, attr: str, default=None):
        """Get the given attribute.
        
        Parameters
        ----------
        attr : str
            Attribute to get.
        default : TYPE, optional
            Default return value. The default is None.

        Returns
        -------
        TYPE
            Value of the attribute.

        """
        data = getattr(self, attr)
        if data == None:
            return default
        elif isinstance(data, str) and data == "not_supported":
            return default
        return data
        

class EnvoyLegacy(BaseGateway):
    """Enphase(R) Envoy-R Gateway using FW < R3.9."""
    
    VERBOSE_NAME = "Envoy-R"
    
    production = RegexDescriptor(
        "production_legacy",
        r"<td>Currentl.*</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(W|kW|MW)</td>"
    )
    
    daily_production = RegexDescriptor(
        "production_legacy",
        r"<td>Today</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>"
    )
    
    seven_days_production = RegexDescriptor(
        "production_legacy",
        r"<td>Past Week</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>"
    )
    
    lifetime_production = RegexDescriptor(
        "production_legacy",
        r"<td>Since Installation</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>"
    )
    

class Envoy(BaseGateway):
    """Enphase(R) Envoy-R Gateway using FW >= R3.9."""
    
    VERBOSE_NAME = "Envoy-R"
    
    _ENDPOINT = "api/v1/production"
    
    production = JsonDescriptor("wattsNow", _ENDPOINT)
    
    daily_production = JsonDescriptor("wattHoursToday", _ENDPOINT)
    
    seven_days_production = JsonDescriptor("whLastSevenDays", _ENDPOINT)
    
    lifetime_production = JsonDescriptor("wattHoursLifetime", _ENDPOINT)
    
    @gateway_property(required_endpoint=_ENDPOINT + "/inverters")
    def inverters_production(self):
        """Single inverter production data."""
        data = self.data.get(self._ENDPOINT + "/inverters")
        if data:
            return {item["serialNumber"]: item for item in data}
            
        return None
        

class EnvoyS(Envoy):
    """Enphase(R) Envoy-S Standard Gateway."""
    
    VERBOSE_NAME = "Envoy-S Standard"
    
    ensemble_inventory = JsonDescriptor("$", "ivp/ensemble/inventory")
    
    ensemble_submod = JsonDescriptor("$", "ivp/ensemble/submod")
    
    ensemble_secctrl = JsonDescriptor("$", "ivp/ensemble/secctrl")
    
    ensemble_power = JsonDescriptor("devices:", "ivp/ensemble/power")
    
    
    
    # @gateway_property(required_endpoint="ivp/ensemble/inventory")
    # def ensemble_inventory(self):
    #     """Ensemble inventory data."""
    #     result = self.data.get("ivp/ensemble/inventory")
    #     #result = JsonDescriptor.resolve("ensemble_inventory", self.data)
    #     storages = {}
    #     if result and isinstance(result, list):
    #         for entry in result:
    #             storage_type = entry.get("type")
    #             if devices := entry.get("devices"):
    #                 for device in devices:
    #                     uid = f"{storage_type.lower()}_{device['serial_num']}" 
    #                     storages[uid] = device 
  
    #     return storages
    
    
    @gateway_property(required_endpoint="ivp/ensemble/inventory")
    def encharge_inventory(self):
        """Ensemble inventory data.
        
        Only return encharge related data.
        
        """
        data = self.data.get("ivp/ensemble/inventory", {})
        result = JsonDescriptor.resolve(
            "[?(@.type=='ENCHARGE')].devices", 
            data,
        )
        if result:
            return {device["serial_num"]: device for device in result}
        
        return None

    @gateway_property(required_endpoint="ivp/ensemble/power")
    def encharge_power(self):
        """Ensemble inventory data.
        
        Only returns encharge related data.
        
        """
        data = self.data.get("ivp/ensemble/power", {})
        result = JsonDescriptor.resolve("devices:", data)
        if result and type(result, list):
            return {device["serial_num"]: device for device in result}
        
        return None        
            
        
        # storages = {}
        # if result and isinstance(result, list):
        #     for entry in result:
        #         storage_type = entry.get("type")
        #         if devices := entry.get("devices"):
        #             for device in devices:
        #                 uid = f"{storage_type.lower()}_{device['serial_num']}" 
        #                 storages[uid] = device 
  
        # return storages
    
    
    
    @gateway_property
    def ac_battery(self) -> ACBattery | None:
        """AC battery data."""
        data = self.data.get("production.json", {})
        result = JsonDescriptor.resolve("storage[?(@.percentFull)]", data)
        return ACBattery(result) if result else None
        
    
    # @gateway_property(required_endpoint="ensemble_submod")
    # def ensemble_submod(self):
    #     """Ensemble submod data."""
    #     result = JsonDescriptor.resolve("ensemble_sbumod", self.data)
    #     return result if result else self._default
        
    # @gateway_property(required_endpoint="ensemble_power")
    # def ensemble_power(self):
    #     """Ensemble power data."""
    #     result = JsonDescriptor.resolve("ensemble_power.devices:", self.data)
    #     return result if result else self._default
    
    # @gateway_property(required_endpoint="ensemble_secctrl")
    # def ensemble_secctrl(self):
    #     """Ensemble secctrl data."""
    #     result = JsonDescriptor.resolve("ensemble_secctrl", self.data)
    #     return result if result else self._default
    
    @gateway_property(required_endpoint="production.json")
    def acb_storage(self):
        """ACB storage data."""
        data = self.data.get("production.json", {})
        result = JsonDescriptor.resolve("storage[?(@.percentFull)]", data)
        return result if result else {}
    
    @gateway_property
    def battery_storage(self):
        """Battery storage data."""
        ensemble_storage = self.ensemble_inventory
        acb_storage = self.acb_storage
        return ensemble_storage | acb_storage

        
class EnvoySMetered(EnvoyS):
    """Enphase(R) Envoy Model S Metered Gateway."""
    
    VERBOSE_NAME = "Envoy-S Metered"
    
    _PRODUCTION = "production[?(@.type=='eim' && @.activeCount > 0)]"
    
    _CONS = "consumption[?(@.measurementType == '{}' && @.activeCount > 0)]"
    
    _TOTAL_CONSUMPTION = _CONS.format("total-consumption")
    
    _NET_CONSUMPTION = _CONS.format("net-consumption")
    
    consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".wNow",
        "production.json",
    )
    
    daily_consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".whToday",
        "production.json",
    )
    
    seven_days_consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".whLastSevenDays",
        "production.json",  
    )
    
    lifetime_consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".whLifetime",
        "production.json",
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.production_ct = None
        self.consumption_ct = None
    
    # @gateway_probe(required_endpoint="production_json")
    # def probe(self):
    #     """Probe the endpoint."""
    #     if self.initial_update_finished:
    #         return 
        
    #     prod_count = JsonDescriptor.resolve(
    #         "production_json.production[?(@.type=='eim')].activeCount", 
    #         self.data
    #     )
        
    #     cons_count = JsonDescriptor.resolve(
    #         "production_json.consumption[?(@.type=='eim')].activeCount", 
    #         self.data
    #     )
    #     if isinstance(cons_count, list):
    #         cons_count = cons_count[0]    
        
    #     self.production_ct = True if prod_count and prod_count > 0 else False
    #     self.consumption_ct = True if cons_count and cons_count > 0 else False
    
    @gateway_probe(required_endpoint="production.json")
    def meters_config(self):
        """Probe the meter settings."""
        if self.initial_update_finished:
            return 
        
        prod_count = JsonDescriptor.resolve(
            "production[?(@.type=='eim')].activeCount", 
            self.data.get("production.json", {}),  
        )
        
        if not prod_count:
            self._PRODUCTION = "production[?(@.type=='inverters')]"
            
        # self.production_ct = True if prod_count and prod_count > 0 else False
        # self.consumption_ct = True if cons_count and cons_count > 0 else False
        
    @gateway_property(required_endpoint="production.json")
    def production(self):
        """Energy production."""
        data = self.data.get("production.json", {})
        return JsonDescriptor.resolve(self._PRODUCTION + ".wNow", data)

    @gateway_property(required_endpoint="production.json")
    def daily_production(self):
        """Todays energy production."""
        data = self.data.get("production.json", {})
        return JsonDescriptor.resolve(self._PRODUCTION + ".whToday", data)
     
    @gateway_property(required_endpoint="production.json")
    def seven_days_production(self):
        """Last seven days energy production."""
        data = self.data.get("production.json", {})
        return JsonDescriptor.resolve(self._PRODUCTION + ".whLastSevenDays", data)
        
    @gateway_property(required_endpoint="production.json")
    def lifetime_production(self):
        """Lifetime energy production."""
        data = self.data.get("production.json", {})
        return JsonDescriptor.resolve(self._PRODUCTION + ".whLifetime", data)

    
    # @gateway_property(required_endpoint="production_json")
    # def consumption(self):
    #     """Current energy consumption."""
    #     if self.consumption_ct:
    #         return JsonDescriptor.resolve(self._CONSMPT_TOTAL + ".wNow", self.data)
    #     else:
    #         return "not_supported"

    # @gateway_property(required_endpoint="production_json")
    # def daily_consumption(self):
    #     """Todays energy consumption."""
    #     if self.consumption_ct:
    #         return JsonDescriptor.resolve(self._CONSMPT_TOTAL + ".whToday", self.data)
    #     else:
    #         return "not_supported"
        
    # @gateway_property(required_endpoint="production_json")
    # def seven_days_consumption(self):
    #     """Last seven days energy consumption."""
    #     if self.consumption_ct:
    #         return JsonDescriptor.resolve(self._CONSMPT_TOTAL + ".whLastSevenDays", self.data)
    #     else:
    #         return "not_supported"
        
    # @gateway_property(required_endpoint="production_json")
    # def lifetime_consumption(self):
    #     """Lifetime energy consumption."""
    #     if self.consumption_ct:
    #         return JsonDescriptor.resolve(self._CONSMPT_TOTAL + ".whLifetime", self.data)
    #     else:
    #         return "not_supported"
    
