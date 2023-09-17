"""Custom exceptions module."""

import httpx


class GatewayError(Exception):
    """Base Exception."""


# Authentication errors --->

class AuthenticationError(GatewayError):
    """Base Exception for authentication errors."""

    def __init__(self, message: str, request=None, response=None):
        super().__init__(message)
        self.request = request
        self.response = response


class EnlightenAuthenticationError(AuthenticationError):
    """Exception raised for a 401 Unauthorized response from Enlighten."""


class GatewayAuthenticationError(AuthenticationError):
    """Exception raised when unable to authenticate to the Enphase gateway."""


class GatewayAuthenticationRequired(AuthenticationError):
    """Exception raised when authentication hasn't been setup."""


# Communication errors --->

class CommunicationError(GatewayError):
    """Base Exception for communication errors.

    Used to specify a httpx.TransportError exception.
    """

    def __init__(self, message: str, request=None):
        super().__init__(message)
        self.request = request


class EnlightenCommunicationError(CommunicationError):
    """Exception raised for communication errors with Enlighten."""


class GatewayCommunicationError(CommunicationError):
    """Exception raised for communication errors with the gateway."""


# EnphaseTokenAuth errors --->

class TokenAuthConfigError(GatewayError):
    """Exception raised for a invalid configuration of EnphaseTokenAuth.

    Raised when the provided combination of arguments is not supported.
    """


class TokenRetrievalError(GatewayError):
    """Exception raised for an unsuccesfull retrieval of a new token.

    Raised if the retrieval of an (R)Enphase token fails.
    """


class InvalidTokenError(GatewayError):
    """Exception raised for invalid Enphase token."""






# Configuration errors:  
    

    

class EnlightenUnauthorized(httpx.HTTPStatusError):
    """Exception raised for 401 Unauthorized response from Enlighten.

    Raised if status 401 is returned while trying to login to enlighten.
    Indicates wrong enlighten credentials.
    
    """
    pass


# Legacy errors --->

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


INVALID_AUTH_ERRORS = (
    GatewayAuthenticationError,
    GatewayAuthenticationRequired
)
