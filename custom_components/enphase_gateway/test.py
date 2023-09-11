import requests
import json
from requests.adapters import HTTPAdapter, Retry
import datetime
import time
from pathlib import Path
import re
#import jwt


def foo():
    raise ValueError
    
    
try:
    foo()
    
except ValueError as err:
    print("error")
    print(err.__class__.__name__)



x = ValueError()

t = x.__class__.__name__




r = re.split('(?<=.)(?=[A-Z])', t)

print(r)



new = "_".join(r).lower()



print(new)
