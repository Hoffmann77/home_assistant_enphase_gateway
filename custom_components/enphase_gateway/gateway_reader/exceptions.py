"""Exceptions module."""

import httpx


class GatewayError(Exception):
    """Base class for gateway reader exceptions."""
    

# Configuration errors:  
    
class TokenAuthConfigError(GatewayError):
    """Exception raised for invalid configuration of EnphaseTokenAuth.
    
    Raised when the provided combination of arguments is not supported.
    
    """    
    
    
# Authentication errors:

class GatewayAuthenticationError(GatewayError):
    """Exception raised when unable to query the Envoy firmware version."""

    def __init__(self, status: str) -> None:
        self.status = status


class GatewayAuthenticationRequired(GatewayError):
    """Exception raised when authentication hasn't been setup."""

    def __init__(self, status: str) -> None:
        self.status = status    
    
    
    
class TokenConfigurationError(ValueError):
    """Exception raised for invalid configuration of EnphaseTokenAuth.
    
    Raised when the provided combination of arguments is not supported.
    
    """


class InvalidEnphaseToken(ValueError):
    """Error for invalid Enphase tokens.
    
    Is raised if token validation using /auth/check_jwt returns
    invalid as response.
    
    """
    
    pass

class EnlightenUnauthorized(httpx.HTTPStatusError):
    """Error for invalid Enlighten credentials.
    
    Is raised if status 401 is returned while trying to login to enlighten.
    
    """
    
    pass

class EnvoyFirmwareCheckError(GatewayError):
    """Exception raised when unable to query the Envoy firmware version."""

    def __init__(self, status_code: int, status: str) -> None:
        self.status_code = status_code
        self.status = status


class EnvoyFirmwareFatalCheckError(GatewayError):
    """Exception raised when we should not retry the Envoy firmware version."""

    def __init__(self, status_code: int, status: str) -> None:
        self.status_code = status_code
        self.status = status
        
        
class EnvoyAuthenticationRequired(GatewayError):
    """Exception raised when authentication hasn't been setup."""

    def __init__(self, status: str) -> None:
        self.status = status
        
INVALID_AUTH_ERRORS = (GatewayAuthenticationError, GatewayAuthenticationRequired)