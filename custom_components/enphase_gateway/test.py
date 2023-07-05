import requests
import json
from requests.adapters import HTTPAdapter, Retry
import datetime
#import jwt


y = None

TEST = "ich teste {protocol} und {host}"

print(f"test {y}")

for x in range(1,2):
    print(x)
    
    
    
def test(**kwargs):
    print(f"{kwargs}")
    

test(x=5)


def test_1(**kwargs):
    print(kwargs)
    test_2(test="test_1", **kwargs)
    
    
    
def test_2(**kwargs):
    print(kwargs)
    

v = {}
try:
    #x = v["home"]
    print(b)
except:
    raise