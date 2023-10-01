import requests
import json
from requests.adapters import HTTPAdapter, Retry
from datetime import datetime, timedelta
import time
from pathlib import Path
#import re
#import numpy as np
#import jwt

limit_endpoints = ["info.xml", "production.json"]
endpoint="info1.xml"

x = False

if limit_endpoints and x:
    print("Skip")


class BaseDescriptor:
    """Base descriptor."""

    def __init__(self, required_endpoint: str, cache: int = 0) -> None:
        """Initialize BaseDescriptor."""
        self._required_endpoint = required_endpoint
        self._cache = cache

    def __set_name__(self, owner, name) -> None:
        """Set name and owner of the descriptor."""
        if owner and name and self._required_endpoint:
            _endpoint = (self._required_endpoint, self._cache)
            owner._gateway_properties[name] = _endpoint


class Foo1():
    
    _gateway_properties = {}
    
    
class Foo2(Foo1):
    _gateway_properties = {}
    prod_foo2 = BaseDescriptor("foo2")


class Foo3(Foo2):
    _gateway_properties = {}
    prod_foo3 = BaseDescriptor("foo3")


class Foo4(Foo2):
    _gateway_properties = {}
    prod_foo4 = BaseDescriptor("foo4")


print(Foo2._gateway_properties)