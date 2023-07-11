"""Module for custom exceptions."""


class TokenError(ValueError):
    """Error for user provided tokens.
    
    Raised when user provided tokens are not valid or could not be validated
    because of other errors.
    
    Can be used in config_flow to handle errors by user provided tokens.
    
    """
    
    pass


class TokenConfigurationError(ValueError):
    """Error for invalid combination of arguments in EnphaseToken.
    
    Raised when the provided combination of arguments in EnphaseToken is
    not supported.
    
    """
    
    pass


class InvalidEnphaseTokenError(ValueError):
    """Error for invalid Enphase tokens.
    
    Is raised if token validation using /auth/check_jwt returns
    invalid as response.
    
    """
    
    pass