import requests
import json
from requests.adapters import HTTPAdapter, Retry
import datetime
#import jwt


TEST = "ich teste {protocol} und {host}"

print(TEST.format(protocol="https", host="test"))
