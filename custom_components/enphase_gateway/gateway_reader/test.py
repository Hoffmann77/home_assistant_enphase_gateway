"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import time
import logging
#import xmltodict
from typing import TYPE_CHECKING, Callable

from httpx import Response

from const import AVAILABLE_PROPERTIES
from endpoint import GatewayEndpoint
from descriptors import ResponseDescriptor, JsonDescriptor, RegexDescriptor 

#from .models.ac_battery import ACBattery

if TYPE_CHECKING:
    from gateway_reader import GatewayReader


_LOGGER = logging.getLogger(__name__)

#GATEWAY_PROPERTIES = {}


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
        """Inner function"""
        _endpoint = None
        if required_endpoint:
            _endpoint = GatewayEndpoint(required_endpoint, cache)
        
        func.gateway_property = _endpoint
        #BaseGateway._gateway_properties[func.__name__] = _endpoint
        return func #property(func)
    
    return decorator if _func is None else decorator(_func)
    

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
    """Base class representing an (R)Enphase Gateway.
    
    Provides properties to access data fetched from the required endpoint. 
    
    Attributes
    ----------
    data : dict
        Response data from the endpoints.
    initial_update_finished : bool
        Return True if the initial update has finished. Return False otherwise.
    
    """
    VERBOSE_NAME = "Enphase Gateway"

    #_gateway_properties = {}
    #_gateway_probes = {}
    
    def __new__(cls, *args, **kwargs):
        """Create a new instance."""
        instance = super().__new__(cls)
        gateway_properties = {}
        gateway_probes = {}

        for obj in [instance.__class__] + instance.__class__.mro():
            for name, method in obj.__dict__.items():
                # add gateway properties that have been added to the classes
                # _gateway_properties dict by descriptors.
                if name == "_gateway_properties":
                    print("Name", name)
                    for key, val in method.items():
                        gateway_properties.setdefault(key, val)

                # catch flagged methods and add to instance's
                # _gateway_properties or _gateway_probes.
                if endpoint := getattr(method, "gateway_property", None):
                    if gateway_properties.setdefault(name, endpoint) is endpoint:
                        setattr(instance.__class__, name, property(method))
                elif endpoint := getattr(method, "gateway_probe", None):
                    gateway_probes.setdefault(name, endpoint)

        instance._gateway_properties = gateway_properties
        instance._gateway_probes = gateway_probes
        return instance
        
        
        
        # print(f"Dir: {dir(cls)} \n")
        # print(f"Dict: {cls.__dict__}\n")
        
        new = [obj.__dict__.items() for obj in [cls] + cls.mro()]
        
        required = {}
        print(new)
        #for obj in [cls] + cls.mro():
        for name, method in new:# obj.__dict__.items():
            
            if name == "_gateway_properties":
                for key, val in method.items():
                    required.setdefault(key, val)    

            #print(name, obj)
            if endpoint := getattr(method, "gateway_property", None):
                required.setdefault(name, endpoint)
                #obj._gateway_properties[name] = endpoint
                setattr(cls, name, property(method))
        
        instance = super().__new__(cls)
        instance._test = required
        
        # print(f"Dict instance:\n")
        for obj in [instance.__class__] + instance.__class__.mro():
            for name, method in obj.__dict__.items():
                pass
                # print(f"Name: {name}  Method: {method}")
        
        
        return instance
    
    
    
    
    def __init__(self) -> None:
        """Initialize instance of BaseGateway."""
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
        """Return all required endpoints.

        Returns
        -------
        endpoints : list[GatewayEndpoint]
            List containing all required endpoints.

        """
        if self._required_endpoints:
            return self._required_endpoints.values()
            
        endpoints = {}

        def update_endpoints(endpoint):
            _endpoint = endpoints.get(endpoint.path)
            
            if _endpoint == None:
                endpoints[endpoint.path] = endpoint
                
            elif endpoint.cache < _endpoint.cache:
                _endpoint.cache = endpoint.cache
        
        _LOGGER.debug(f"properties registered: {self._gateway_properties.items()}")
        #for prop, prop_endpoint in GATEWAY_PROPERTIES.items():
        
   
        
        required = {}
        for obj in [self.__class__] + self.__class__.mro():
            for name, method in obj.__dict__.items():
                if name == "_gateway_properties":
                    for key, val in method.items():
                        required.setdefault(key, val)
        
        #print(f"required: {required} \n")
        
        
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
                
        return endpoints.values()
    
    # def register_property(endpoint, name):
    #     GATEWAY_PROPERTIES[name] = endpoint
        
     
    # def update_required_endpoints(self):
        
    #     endpoints_new = {}
    #     for endpoint in self._gateway_properties:
    #         _endpoint = endpoints_new.get(endpoint.path)
    #         if _endpoint == None:
    #             endpoints_new[endpoint.path] = endpoint
            
    #         elif endpoint.cache < _endpoint.cache:
    #             _endpoint.cache = endpoint.cache
            
            
            
            

    def get_subclass(self):
        """Return the matching subclass."""
        
        # probe first
        # 
    
    
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
            self.data[endpoint.path] = response.json()
        elif content_type in ("text/xml", "application/xml"):
            pass
            #self.data[endpoint.path] = xmltodict.parse(response.text)
        elif content_type == "text/html":
            self.data[endpoint.path] = response.text
        else:
            self.data[endpoint.path] = response.text

    def probe(self):
        """Probe all probes."""
        for probe in self._gateway_probes.keys():
            func = getattr(self, probe)
            func()

    def __getattribute__(self, name):
        """Return None if gateway does not support this property."""
        try:
            value = object.__getattribute__(self, name)
        except AttributeError as err:
            if name in AVAILABLE_PROPERTIES:
                return None
            else:
                raise err
        else:
            return value

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
        if data is None:
            return default
        elif isinstance(data, str) and data == "not_supported":
            return default
        return data
        

class EnvoyLegacy(BaseGateway):
    """Enphase(R) Envoy-R Gateway using FW < R3.9."""
    #_gateway_properties = {}
    VERBOSE_NAME = "Envoy-R"
    
    #_gateway_properties = {}
    
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
    #_gateway_properties = {}
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
    #_gateway_properties = {}
    VERBOSE_NAME = "Envoy-S Standard"
    
    ensemble_inventory = JsonDescriptor("", "ivp/ensemble/inventory")
    
    ensemble_submod = JsonDescriptor("", "ivp/ensemble/submod")
    
    ensemble_secctrl = JsonDescriptor("", "ivp/ensemble/secctrl")
    
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
            "$.[?(@.type=='ENCHARGE')].devices", 
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
        if result and isinstance(result, list):
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
    def ac_battery(self) ->  None:
        """AC battery data."""
        data = self.data.get("production.json", {})
        result = JsonDescriptor.resolve("storage[?(@.percentFull)]", data)
        return None
        
    
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
    """Enphase(R) Envoy Model S Metered Gateway.
    
    This is the default gateway for metered envoy-s gateways.
    It further provides the method 'get_abnormal' to get the 
    """
    #_gateway_properties = {}
    
    VERBOSE_NAME = "Envoy-S Metered"
    
    _PRODUCTION_JSON = "production[?(@.type=='eim' && @.activeCount > 0)].{}"
    
    _TOTAL_CONSUMPTION = "consumption[?(@.measurementType == 'total-consumption' && @.activeCount > 0)].{}"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meters = None
        self.production_ct = None
        self.consumption_ct = None
        
        self.performance_mode = True
        
        self.production_meter = None
        self.net_consumption_meter = None
        self.total_consumption_meter = None
        
    @gateway_probe(required_endpoint="ivp/meters")
    def ivp_meters_probe(self):
        """Probe the meters configuration."""
        
        base_expr = "$.[?(@.state=='enabled' && @.measurementType=='{}')].eid"
        
        self.production_meter = JsonDescriptor.resolve(
            base_expr.format("production"),
            self.data.get("ivp/meters", {}),
        )
        self.net_consumption_meter = JsonDescriptor.resolve(
            base_expr.format("net-consumption"),
            self.data.get("ivp/meters", {}),
        )
        self.total_consumption_meter = JsonDescriptor.resolve(
            base_expr.format("total-consumption"),
            self.data.get("ivp/meters", {}),
        )    
        
    
    @gateway_property(required_endpoint="ivp/meters/readings")
    def grid_import(self):
        """Return grid import."""
        # TODO: implement
        return None
        
    @gateway_property(required_endpoint="ivp/meters/readings")  
    def grid_import_lifetime(self):
        """Return lifetime grid import."""
        # TODO: implement
        return None
        
    @gateway_property(required_endpoint="ivp/meters/readings")  
    def grid_export(self):
        """Return grid export."""
        # TODO: implement
        return None
        
    @gateway_property(required_endpoint="ivp/meters/readings")    
    def grid_export_lifetime(self):
        """Return lifetime grid export."""
        # TODO: implement
        return None

    
    
    
    @gateway_property(required_endpoint="ivp/meters/readings")
    def production(self):
        """Return the measured active power."""
        return JsonDescriptor.resolve(
            f"$.[?(@.eid=='{self.production_meter}')].activePower",
            self.data.get("ivp/meters/readings", {})
        )
    
    @gateway_property(required_endpoint="production.json", cache=120)
    def daily_production(self):
        """Return the daily energy production."""
        if self.performance_mode is False:
            return JsonDescriptor.resolve(
                self._PRODUCTION_JSON.format("whToday"),
                self.data.get("production.json", {})
            )
        return None
            
    @gateway_property(required_endpoint="production.json", cache=120)
    def seven_days_production(self):
        """Return the daily energy production."""
        if self.performance_mode is False:
            return JsonDescriptor.resolve(
                self._PRODUCTION_JSON.format("whLastSevenDays"),
                self.data.get("production.json", {}),
            )
        return None       
        
    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_production(self):
        """Return the lifetime energy production."""
        return JsonDescriptor.resolve(
            f"$.[?(@.eid=='{self.production_meter}')].actEnergyDlvd",
            self.data.get("ivp/meters/readings", {})
        )
        

    @gateway_property(required_endpoint="ivp/meters/readings")
    def consumption(self):
        """Return the measured active power."""
        if eid := self.net_consumption_meter:
            prod = self.production
            cons = JsonDescriptor.resolve(
                f"$.[?(@.eid=='{eid}')]",
                self.data.get("ivp/meters/readings", {})
            )
            return prod + cons["actPower"]
            
    @gateway_property(required_endpoint="production.json", cache=120)
    def daily_consumption(self):
        """Return the daily energy production."""
        if self.performance_mode is False:
            return JsonDescriptor.resolve(
                self._TOTAL_CONSUMPTION.format("whToday"),
                self.data.get("production.json", {})
            )
        return None
            
    @gateway_property(required_endpoint="production.json", cache=120)
    def seven_days_consumption(self):
        """Return the daily energy production."""
        if self.performance_mode is False:
            return JsonDescriptor.resolve(
                self._TOTAL_CONSUMPTION.format("whLastSevenDays"),
                self.data.get("production.json", {}),
            )
        return None       
        
    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_consumption(self):
        """Return the lifetime energy production."""
        if eid := self.net_consumption_meter:
            prod = self.lifetime_production
            cons = JsonDescriptor.resolve(
                f"$.[?(@.eid=='{eid}')]",
                self.data.get("ivp/meters/readings", {})
            )
            return prod - (cons["actEnergyRcvd"] - cons["actEnergyDlvd"])
        

    
    
    
    
        
class EnvoySMeteredAbnormal(EnvoyS):
    """Enphase(R) Envoy Model S Metered Gateway."""
    #_gateway_properties = {}
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
        self.meters = None
        self.production_ct = None
        self.consumption_ct = None

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
        data = self.data.get("production.json1", {})
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
    

#print(EnvoyS._gateway_properties)
#print("")
gateway = EnvoySMetered()

#print(Envoy.inverters_production)


#print("Required endpoints: ", gateway._gateway_properties)
print(gateway._gateway_properties)
print("")
print(gateway.required_endpoints)

print(gateway.production)



