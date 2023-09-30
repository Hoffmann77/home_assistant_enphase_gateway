import requests
import json
from requests.adapters import HTTPAdapter, Retry
from datetime import datetime, timedelta
import time
from pathlib import Path
#import re
#import numpy as np
#import jwt


def foo():
    x = 5
    print("foo")
    

f = foo
f.test = "test"
print(f.__dict__)