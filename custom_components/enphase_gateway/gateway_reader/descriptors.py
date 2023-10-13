"""Enphase(R) Gateway data descriptor module."""

import re
import logging
from textwrap import dedent

from jsonpath import jsonpath

from .endpoint import GatewayEndpoint


_LOGGER = logging.getLogger(__name__)


class BaseDescriptor:
    """Base descriptor."""

    def __init__(self, required_endpoint: str, cache: int = 0) -> None:
        """Initialize BaseDescriptor."""
        self._required_endpoint = required_endpoint
        self._cache = cache

    def __set_name__(self, owner, name) -> None:
        """Set name and owner of the descriptor."""
        self._name = name
        if owner and name and self._required_endpoint:
            _endpoint = GatewayEndpoint(self._required_endpoint, self._cache)
            uid = f"{owner.__name__.lower()}_gateway_properties"
            if properties := getattr(owner, uid, None):
                properties[name] = _endpoint
            else:
                setattr(owner, uid, {name: _endpoint})


class PropertyDescriptor(BaseDescriptor):
    """Property descriptor.

    A pure python implementation of property that registers the
    required endpoint and the caching interval.
    """

    def __init__(
            self,
            fget=None,
            doc=None,
            required_endpoint: str | None = None,
            cache: int = 0,
    ) -> None:
        """Initialize instance of PropertyDescriptor."""
        super().__init__(required_endpoint, cache)
        self.fget = fget
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
        self._name = ''

    def __get__(self, obj, objtype=None):
        """Magic method. Return the response of the fget function."""
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError(f"property '{self._name}' has no getter")
        return self.fget(obj)

    # def getter(self, fget):
    #     prop = type(self)(fget, self.fset, self.fdel, self.__doc__)
    #     prop._name = self._name
    #     return prop


class ResponseDescriptor(BaseDescriptor):
    """Descriptor returning the raw response."""

    def __get__(self, obj, objtype):
        """Magic method. Return the response data."""
        data = obj.data.get(self._required_endpoint, {})
        return data


class JsonDescriptor(BaseDescriptor):
    """JasonPath gateway property descriptor."""

    def __init__(
            self,
            jsonpath_expr: str,
            required_endpoint: str | None = None,
            cache: int = 0,
    ) -> None:
        super().__init__(required_endpoint, cache)
        self.jsonpath_expr = jsonpath_expr

    def __get__(self, obj, objtype=None):
        """Magic method. Resolve the jasonpath expression."""
        if self._required_endpoint:
            data = obj.data.get(self._required_endpoint, {})
        else:
            data = obj.data or {}
        return self.resolve(self.jsonpath_expr, data)

    @classmethod
    def resolve(cls, path: str, data: dict, default: str | int | float = None):
        """Classmethod to resolve a given JsonPath."""
        _LOGGER.debug(f"Resolving jsonpath: {path} using data: {data}")
        if path == "":
            return data
        result = jsonpath(data, dedent(path))
        if result is False:
            _LOGGER.debug(
                f"The configured jsonpath: {path}, did not return anything!"
            )
            return default

        if isinstance(result, list) and len(result) == 1:
            result = result[0]

        _LOGGER.debug(f"The configured jsonpath: {path}, did return {result}")
        return result


class RegexDescriptor(BaseDescriptor):
    """Regex gateway property descriptor."""

    def __init__(self, required_endpoint, regex, cache: int = 0):
        super().__init__(required_endpoint, cache)
        self._regex = regex

    def __get__(self, obj, objtype=None):
        """Magic method. Resolve the regex expression."""
        data = obj.data.get(self._required_endpoint, "")
        return self.resolve(self._regex, data)

    @classmethod
    def resolve(cls, regex: str, data: str):
        """Classmethod to resolve a given REGEX."""
        text = data
        match = re.search(regex, text, re.MULTILINE)
        if match:
            if match.group(2) in {"kW", "kWh"}:
                result = float(match.group(1)) * 1000
            elif match.group(2) in {"mW", "MWh"}:
                result = float(match.group(1)) * 1000000
            else:
                result = float(match.group(1))
        else:
            _LOGGER.debug(
                f"The configured REGEX: {regex}, did not return anything!"
            )
            return None

        f"The configured REGEX: {regex}, did return {result}"
        return result
