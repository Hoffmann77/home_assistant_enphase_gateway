"""Enphase(R) Gateway data descriptor classes."""

import re
import logging
from textwrap import dedent

from jsonpath import jsonpath

from .endpoint import GatewayEndpoint


_LOGGER = logging.getLogger(__name__)


class BaseDescriptor:
    """Base descriptor."""
    
    def __init__(self, required_endpoint: str, cache: int) -> None:
        """Initialize BaseDescriptor."""
        self._required_endpoint = required_endpoint
        self._cache = cache
        self._name = None
        self._owner = None
        
    def __set_name__(self, owner, name) -> None:
        """Set name and owner of the descriptor."""
        self._name=name
        self._owner=owner
        
    def _register_property(self):
        """Register required_endpoint if required_endpoint is not None.
        
        Add required_endpoint to self._owner._gateway_properties
        
        """
        if self._owner and self._name and self._required_endpoint:
            _endpoint = GatewayEndpoint(self._required_endpoint, self._cache)
            self._owner._gateway_properties[self._name] = _endpoint


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
        self._register_property()
    
    def __get__(self, obj, objtype=None):
        """Magic method. Resolve the jasonpath expression."""
        if self._required_endpoint:
            data = obj.data.get(self._required_endpoint, {})
        else:
            data = obj.data or {}
        return self.resolve(self.jsonpath_expr, data)

    @classmethod
    def resolve(cls, path: str, data: dict, default: str | int | float = None):
        """Classmethod to resolve a given JsonPath.
        
        Parameters
        ----------
        path : str
            Jasonpath expression.
        data : dict
            Dict containing the enpoint results.
        default : str or int or float, optional
            Default return value. The default is None.

        Returns
        -------
        TYPE
            DESCRIPTION.

        """
        _LOGGER.debug(f"Resolving jsonpath: {path} using data: {data.keys()}")
        result = jsonpath(data, dedent(path))
        if result == False:
            _LOGGER.debug(
                f"The configured jsonpath: {path}, did not return anything!"
            )
            return default

        if isinstance(result, list) and len(result) == 1:
            result = result[0]
        
        _LOGGER.debug(f"Success resolving jsonpath: {path} result: {result}")
        return result    


class RegexDescriptor(BaseDescriptor):
    """Regex gateway property descriptor."""
    
    def __init__(self, required_endpoint, regex, cache: int = 0):
        super().__init__(required_endpoint, cache)
        self.regex = regex
        self._register_property()

    def __get__(self, obj, objtype=None):
        """Magic method. Resolve the regex expression."""
        data = obj.data.get(self.required_endpoint, "")
        return self.resolve(self.regex, data)

    @classmethod
    def resolve(cls, regex: str, data: str):
        """Classmethod to resolve a given REGEX."""
        text = data
        match = re.search(regex, text, re.MULTILINE)
        if match:
            if match.group(2) in {"kW", "kWh"}:
                result = float(match.group(1)) * 1000
            else:
                if match.group(2) in {"mW", "MWh"}:
                    result = float(match.group(1)) * 1000000
                else:
                    result = float(match.group(1))
        else:
            _LOGGER.debug(
                f"The configured REGEX: {regex}, did not return anything!"
            )
            return None
        
        return result

