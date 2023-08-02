import requests
import json
from requests.adapters import HTTPAdapter, Retry
import datetime
import time
#import jwt



class Endpoint:
    
    def __init__(self, name, cache=0):
        self.name = name
        self.url = "test/url"
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

d = {
     "production": Endpoint("production"),
     "consumption": Endpoint("consumption"), 
     "ensemble": Endpoint("ensemble"),
}

s = (Endpoint("production"), Endpoint("consumption"))

x = {}

for endpoint in s:
    
    print(endpoint)
    x[endpoint] = endpoint.url
    
print(x)

    



def test_property(_func=None, **kwargs):
    endpoint = kwargs.pop("required_endpoint", None)


    def decorator(func, *args):
        
        
        def inner(self, *args, **kwargs):
            print(self.test)
            print("inner", type(self))
            return func(self, *args, **kwargs)
            #return property(func(*args, **kwargs))
        
        return inner
        # print("args:", args)
        # print("func:", func)
        # print(type(Gateway))
        # #return func()
        # Gateway.test[func.__name__] = 1
        # return property(func)
    
    
    if _func == None:
        return decorator
    else:
        return decorator(_func)










    