import requests
import json
from requests.adapters import HTTPAdapter, Retry
from datetime import datetime, timedelta
import time
from pathlib import Path
#import re
#import numpy as np
#import jwt

prod = "3"
        
print(prod.__class__.__name__)