"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import logging
from typing import Callable

import xmltodict
from httpx import Response

from homeassistant.util import dt as dt_util

from .const import AVAILABLE_PROPERTIES
from .endpoint import GatewayEndpoint
from .descriptors import (
    PropertyDescriptor,
    ResponseDescriptor,
    JsonDescriptor,
    RegexDescriptor,
)

from .models import (
    ACBatteryStorage,
    EnsemblePowerDevices,
    EnsembleInventory,
)


_LOGGER = logging.getLogger(__name__)


def gateway_property(
        _func: Callable | None = None,
        **kwargs: dict,
) -> PropertyDescriptor:
    """Decorate the given method as gateway property.

    Works identical to the python property decorator.
    Additionally registers the method to the '_gateway_properties' dict
    of the methods parent class.

    Parameters
    ----------
    _func : Callable, optional
        Method to decorate. The default is None.
    **kwargs : dict
        Optional keyword arguments.

    Returns
    -------
    PropertyDescriptor
        Property descriptor calling the method on attribute access.

    """
    required_endpoint = kwargs.pop("required_endpoint", None)
    cache = kwargs.pop("cache", 0)

    def decorator(func):
        return PropertyDescriptor(
            fget=func,
            doc=None,
            required_endpoint=required_endpoint,
            cache=cache,
        )

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
        endpoint = None
        if required_endpoint:
            endpoint = GatewayEndpoint(required_endpoint, cache)

        func.gateway_probe = endpoint
        return func

    return decorator if _func is None else decorator(_func)


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

    def __new__(cls, *args, **kwargs):
        """Create a new instance.

        Catch methods having the 'gateway_property' attribute and add them
        to the classes '_gateway_properties' attribute.
        Set the method as a property of the class.

        """
        instance = super().__new__(cls)
        gateway_properties = {}
        gateway_probes = {}

        for obj in [instance.__class__] + instance.__class__.mro():
            owner_uid = f"{obj.__name__.lower()}"
            for attr_name, attr_val in obj.__dict__.items():
                # add gateway properties that have been added to the classes
                # _gateway_properties dict by descriptors.
                if attr_name == f"{owner_uid}_gateway_properties":
                    for key, val in attr_val.items():
                        gateway_properties.setdefault(key, val)

                # catch flagged methods and add to instance's
                # _gateway_properties or _gateway_probes.
                if endpoint := getattr(attr_val, "gateway_probe", None):
                    gateway_probes.setdefault(attr_name, endpoint)

        instance._gateway_properties = gateway_properties
        instance._gateway_probes = gateway_probes
        return instance

    def __init__(self, gateway_info=None) -> None:
        """Initialize instance of BaseGateway."""
        self.data = {}
        self.gateway_info = gateway_info
        self.initial_update_finished = False
        self._required_endpoints = None
        self._probes_finished = False

    @property
    def properties(self):
        """Return the properties of the gateway."""
        return self._gateway_properties.keys()

    @property
    def all_values(self) -> dict:
        """Return a dict containing all attributes and their value."""
        result = {}
        for attr in self.properties:
            result[attr] = getattr(self, attr)

        return result

    @property
    def required_endpoints(self) -> list[GatewayEndpoint]:
        """Return all required endpoints for this gateway.

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

            if _endpoint is None:
                endpoints[endpoint.path] = endpoint

            elif endpoint.cache < _endpoint.cache:
                _endpoint.cache = endpoint.cache

        _LOGGER.debug(f"Registered properties: {self._gateway_properties}")
        for prop, prop_endpoint in self._gateway_properties.items():
            if isinstance(prop_endpoint, GatewayEndpoint):

                if self.initial_update_finished:
                    # When the value is None or empty list or dict,
                    # then the endpoint is useless for this token,
                    # so we do not require it.
                    if (val := getattr(self, prop)) in (None, [], {}):
                        _LOGGER.debug(
                            f"Skip property: {prop} : {prop_endpoint} : {val}"
                        )
                        continue

                update_endpoints(prop_endpoint)

        if self.initial_update_finished:
            # Save list in memory, as we should not evaluate this list again.
            # If the list needs re-evaluation, then reload the plugin.
            self._required_endpoints = endpoints

        else:
            for probe, probe_endpoint in self._gateway_probes.items():
                if isinstance(probe_endpoint, GatewayEndpoint):
                    update_endpoints(probe_endpoint)

        return endpoints.values()

    def get_subclass(self):
        """Return the matching subclass."""
        return None

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
        _LOGGER.debug(
            f"Setting endpoint data: {endpoint} : {response.content}"
        )
        if content_type == "application/json":
            self.data[endpoint.path] = response.json()
        elif content_type in ("text/xml", "application/xml"):
            self.data[endpoint.path] = xmltodict.parse(response.text)
        elif content_type == "text/html":
            self.data[endpoint.path] = response.text
        else:
            self.data[endpoint.path] = response.text

    def run_probes(self):
        """Run all registered probes of the gateway."""
        _LOGGER.debug(f"Registered probes: {self._gateway_probes.keys()}")
        for probe in self._gateway_probes.keys():
            func = getattr(self, probe)
            func()
            self._probes_finished = True

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

    VERBOSE_NAME = "Envoy-R"

    production = RegexDescriptor(
        r"<td>Currentl.*</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(W|kW|MW)</td>",
        "production",
    )

    daily_production = RegexDescriptor(
        r"<td>Today</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>",
        "production",
    )

    seven_days_production = RegexDescriptor(
        r"<td>Past Week</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>",
        "production",
    )

    lifetime_production = RegexDescriptor(
        r"<td>Since Installation</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>", # noqa
        "production",
    )


class Envoy(BaseGateway):
    """Enphase(R) Envoy-R Gateway using FW >= R3.9."""

    VERBOSE_NAME = "Envoy-R"

    production = JsonDescriptor("wattsNow", "api/v1/production")

    daily_production = JsonDescriptor("wattHoursToday", "api/v1/production")

    seven_days_production = JsonDescriptor(
        "wattHoursSevenDays", "api/v1/production"
    )

    lifetime_production = JsonDescriptor(
        "wattHoursLifetime", "api/v1/production"
    )

    @gateway_property(required_endpoint="api/v1/production/inverters")
    def inverters(self):
        """Single inverter production data."""
        inverters = self.data.get("api/v1/production/inverters")
        if inverters:
            return {inv["serialNumber"]: inv for inv in inverters}

        return None


class EnvoyS(Envoy):
    """Enphase(R) Envoy-S Standard Gateway."""

    VERBOSE_NAME = "Envoy-S Standard"

    ensemble_secctrl = JsonDescriptor("", "ivp/ensemble/secctrl")

    @gateway_property(required_endpoint="ivp/ensemble/inventory")
    def ensemble_inventory(self) -> EnsembleInventory | None:
        """Ensemble Encharge storages."""
        result = JsonDescriptor.resolve(
            "$.[?(@.type=='ENCHARGE')].devices",
            self.data.get("ivp/ensemble/inventory", {}),
        )
        if result and isinstance(result, list):
            return {
                device["serial_num"]: EnsembleInventory.from_result(device)
                for device in result
            }

        return None

    @gateway_property(required_endpoint="ivp/ensemble/power")
    def ensemble_power(self) -> EnsemblePowerDevices | None:
        """Ensemble power data."""
        result = JsonDescriptor.resolve(
            "devices:", self.data.get("ivp/ensemble/power", {})
        )
        if result and isinstance(result, list):
            return EnsemblePowerDevices.from_result(result)

        return None

    @gateway_property(required_endpoint="production.json")
    def ac_battery(self) -> ACBatteryStorage | None:
        """Return AC battery storage data."""
        # AC-Battery is installed when the 'percentFull' key exists.
        data = JsonDescriptor.resolve(
            "storage[?(@.percentFull)]",
            self.data.get("production.json", {})
        )
        if data is not None:
            return ACBatteryStorage.from_result(data)

        return None


class EnvoySMetered(EnvoyS):
    """Enphase(R) Envoy Model S Metered Gateway.

    This is the default gateway for metered Envoy-s gateways.
    It provides probes to detect abnormal configurations.

    """

    VERBOSE_NAME = "Envoy-S Metered"

    _CONS = "consumption[?(@.measurementType == '{}' && @.activeCount > 0)]"

    _PRODUCTION_JSON = "production[?(@.type=='eim' && @.activeCount > 0)].{}"

    _TOTAL_CONSUMPTION_JSON = _CONS.format("total-consumption")

    _NET_CONSUMPTION_JSON = _CONS.format("net-consumption")

    def __init__(self, *args, **kwargs):
        """Initialize instance of EnvoySMetered."""
        super().__init__(*args, **kwargs)
        self.production_meter = None
        self.net_consumption_meter = None
        self.total_consumption_meter = None

    def get_subclass(self):
        """Return the subclass for abnormal gateway installations."""
        if self._probes_finished:
            consumption_meter = (
                self.net_consumption_meter or self.total_consumption_meter
            )
            if not self.production_meter or not consumption_meter:
                return EnvoySMeteredCtDisabled(
                    self.production_meter,
                    self.net_consumption_meter,
                    self.total_consumption_meter,
                )

        return None

    @gateway_probe(required_endpoint="ivp/meters")
    def ivp_meters_probe(self):
        """Probe the meter configuration."""
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
        _LOGGER.debug("Probe: 'ivp_meters_probe' finished")

    # @gateway_property(required_endpoint="ivp/meters/readings")
    # def grid_import(self):
    #     """Return grid import."""
    #     if eid := self.net_consumption_meter:
    #         power = JsonDescriptor.resolve(
    #             f"$.[?(@.eid=={eid})].activePower",
    #             self.data.get("ivp/meters/readings", {})
    #         )
    #         if isinstance(power, (int, float)):
    #             return power if power > 0 else 0

    #     return None

    # @gateway_property(required_endpoint="ivp/meters/readings")
    # def grid_import_lifetime(self):
    #     """Return lifetime grid import."""
    #     if eid := self.net_consumption_meter:
    #         return JsonDescriptor.resolve(
    #             f"$.[?(@.eid=={eid})].actEnergyDlvd",
    #             self.data.get("ivp/meters/readings", {})
    #         )

    #     return None

    # @gateway_property(required_endpoint="ivp/meters/readings")
    # def grid_export(self):
    #     """Return grid export."""
    #     if eid := self.net_consumption_meter:
    #         power = JsonDescriptor.resolve(
    #             f"$.[?(@.eid=={eid})].activePower",
    #             self.data.get("ivp/meters/readings", {})
    #         )
    #         if isinstance(power, (int, float)):
    #             return (power * -1) if power < 0 else 0

    #     return None

    # @gateway_property(required_endpoint="ivp/meters/readings")
    # def grid_export_lifetime(self):
    #     """Return lifetime grid export."""
    #     if eid := self.net_consumption_meter:
    #         return JsonDescriptor.resolve(
    #             f"$.[?(@.eid=={eid})].actEnergyRcvd",
    #             self.data.get("ivp/meters/readings", {})
    #         )

    #     return None

    @gateway_property(required_endpoint="ivp/meters/readings")
    def production(self):
        """Return the measured active power."""
        return JsonDescriptor.resolve(
            f"$.[?(@.eid=={self.production_meter})].activePower",
            self.data.get("ivp/meters/readings", {})
        )

    @gateway_property(required_endpoint="production.json", cache=0)
    def daily_production(self):
        """Return the daily energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION_JSON.format("whToday"),
            self.data.get("production.json", {})
        )

    # @gateway_property(required_endpoint="production.json", cache=0)
    # def seven_days_production(self):
    #     """Return the daily energy production."""
    #     return JsonDescriptor.resolve(
    #         self._PRODUCTION_JSON.format("whLastSevenDays"),
    #         self.data.get("production.json", {}),
    #     )

    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_production(self):
        """Return the lifetime energy production."""
        return JsonDescriptor.resolve(
            f"$.[?(@.eid=={self.production_meter})].actEnergyDlvd",
            self.data.get("ivp/meters/readings", {})
        )

    @gateway_property(required_endpoint="ivp/meters/readings")
    def consumption(self):
        """Return the measured active power."""
        if eid := self.net_consumption_meter:
            prod = self.production
            cons = JsonDescriptor.resolve(
                f"$.[?(@.eid=={eid})].activePower",
                self.data.get("ivp/meters/readings", {})
            )
            if prod and cons:
                return prod + cons
        elif eid := self.total_consumption_meter:
            return JsonDescriptor.resolve(
                f"$.[?(@.eid=={eid})].activePower",
                self.data.get("ivp/meters/readings", {})
            )

        return None

    @gateway_property(required_endpoint="production.json", cache=0)
    def daily_consumption(self):
        """Return the daily energy production."""
        return JsonDescriptor.resolve(
            self._TOTAL_CONSUMPTION_JSON + ".whToday",
            self.data.get("production.json", {})
        )

    # @gateway_property(required_endpoint="production.json", cache=0)
    # def seven_days_consumption(self):
    #     """Return the daily energy production."""
    #     return JsonDescriptor.resolve(
    #         self._TOTAL_CONSUMPTION_JSON + ".whLastSevenDays",
    #         self.data.get("production.json", {}),
    #     )

    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_consumption(self):
        """Return the lifetime energy production."""
        if eid := self.net_consumption_meter:
            prod = self.lifetime_production
            cons = JsonDescriptor.resolve(
                f"$.[?(@.eid=={eid})]",
                self.data.get("ivp/meters/readings", {})
            )
            if prod and cons:
                return prod - (cons["actEnergyRcvd"] - cons["actEnergyDlvd"])
        elif eid := self.total_consumption_meter:
            # TODO: collect fixtures and validate
            return JsonDescriptor.resolve(
                f"$.[?(@.eid=={eid})].actEnergyRcvd",
                self.data.get("ivp/meters/readings", {})
            )

        return None


class EnvoySMeteredCtDisabled(EnvoyS):
    """Enphase(R) Envoy Model S Metered Gateway with disabled CTs."""

    VERBOSE_NAME = "Envoy-S Metered without CTs"

    _CONS = "consumption[?(@.measurementType == '{}' && @.activeCount > 0)]"

    _PRODUCTION = "production[?(@.type=='{}' && @.activeCount > 0)]"

    _PRODUCTION_INV = "production[?(@.type=='inverters')]"

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

    # seven_days_consumption = JsonDescriptor(
    #     _TOTAL_CONSUMPTION + ".whLastSevenDays",
    #     "production.json",
    # )

    lifetime_consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".whLifetime",
        "production.json",
    )

    def __init__(
            self,
            production_meter: str | None,
            net_consumption_meter: str | None,
            total_consumption_meter: str | None,
            *args,
            **kwargs
    ):
        """Initialize instance of EnvoySMeteredAbnormal."""
        super().__init__(*args, **kwargs)
        self.production_meter = production_meter
        self.net_consumption_meter = net_consumption_meter
        self.total_consumption_meter = total_consumption_meter
        self.prod_type = "eim" if production_meter else "inverters"

    @gateway_property(required_endpoint="production.json")
    def production(self):
        """Energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION.format(self.prod_type) + ".wNow",
            self.data.get("production.json", {})
        )

    @gateway_property(required_endpoint="production.json")
    def daily_production(self):
        """Todays energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION.format(self.prod_type) + ".whToday",
            self.data.get("production.json", {})
        )

    # @gateway_property(required_endpoint="production.json")
    # def seven_days_production(self):
    #     """Last seven days energy production."""
    #     return JsonDescriptor.resolve(
    #         self._PRODUCTION.format(self.prod_type) + ".whLastSevenDays",
    #         self.data.get("production.json", {})
    #     )

    @gateway_property(required_endpoint="production.json")
    def lifetime_production(self):
        """Lifetime energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION.format(self.prod_type) + ".whLifetime",
            self.data.get("production.json", {})
        )
