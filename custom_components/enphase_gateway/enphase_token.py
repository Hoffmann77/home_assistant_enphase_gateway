"""Provide the EnphaseToken class for the envoy_reader module."""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import httpx
import jwt
from bs4 import BeautifulSoup

from .http import async_get, async_post
from .exceptions import TokenConfigurationError, InvalidEnphaseToken, EnlightenUnauthorized


_LOGGER = logging.getLogger(__name__)

ENDPOINT_URL_CHECK_JWT = "https://{}/auth/check_jwt"

ENLIGHTEN_LOGIN_URL = "https://enlighten.enphaseenergy.com/login/login.json?"
ENLIGHTEN_TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"

BASE_DIR = Path(__file__).resolve().parent


class EnphaseToken:
    """Class providing functions around an Enphase Token."""
    
    def __init__(
            self,
            host,
            enlighten_username,
            enlighten_password,
            gateway_serial_num,
            token_raw=None,
            token_store=None,
            cache_token=False,
            expose_token=False,
            exposure_path=None,
        ):
        """Initialize EnphaseToken.
        
        Parameters
        ----------
        host : str
            Host ip adress.
        enlighten_username : str
            Enlighten username.
        enlighten_password : TYPE
            Enlighten password.
        gateway_serial_num : TYPE
            Gateway's serial number.
        token_raw : str, optional
            Raw Enphase Token. The default is None.
        token_store : Store, optional
            Home Assistant Store. The default is None.
        cache_token : bool, optional
            Cache token in Store if True. The default is False.
        expose_token : bool, optional
            Expose token to exposure_path if True. The default is False.
        exposure_path : str, optional
            Exposure filepath. The default is None.

        Raises
        ------
        TokenConfigurationError
            Raises if the the combination of arguments is not supported.

        Returns
        -------
        None.

        """
        self.host = host
        self.enlighten_username = enlighten_username
        self.enlighten_password = enlighten_password
        self.gateway_serial_num = gateway_serial_num
        self.expiration_date = None
        self._token_store = token_store
        self._token_store_data = None
        self._cache_token = cache_token if not token_raw else False
        self._expose_token = expose_token
        self._exposure_path = None
        self._token = None
        self._type = None
        self._cookies = None
        
        if (enlighten_username and enlighten_password and gateway_serial_num):
            self._auto_renewal = True
        elif token_raw:
            self._auto_renewal = False
        else:
            msg = (
                "Token Configuration invalid." 
                +" Please provide Enlighten credentials or a raw token." 
            )
            raise TokenConfigurationError(msg)
        
        if token_store:
            self._token_store_data = await token_store.async_load()
            
        if exposure_path:
            self._exposure_path = Path(exposure_path).resolve()
        else:
            self._exposure_path = BASE_DIR.joinpath("exposed_token.json")

        if token_raw:
            self._init_from_token_raw(token_raw)

    @property
    def token(self):
        """Return the plain Enphase token as string.
        
        Returns
        -------
        token : str
            Enphase token as string.

        """
        return self._token 

    @property
    def cookies(self):
        """Return the session cookies.
        
        Returns
        -------
        cookies : dict
            Dict containing the cookies.

        """
        return self._cookies
    
    @property
    def is_populated(self):
        """Return the population status of the EnphaseToken.
        
        Check if self._token and self.expiration_date are populated.
        
        Returns
        -------
        bool
            True if populated. False otherwise.

        """
        if self._token and self.expiration_date:
            return True
        else:
            return False
    
    @property
    def is_expired(self, buffer=600):
        """Return the expiration status of the Enphase token.
        
        Returns
        -------
        bool
            True if token is expired. False otherwise.

        """
        delta = timedelta(seconds=buffer) 
        exp_time = self.expiration_date - delta
        if datetime.now(tz=timezone.utc) <= exp_time:
            _LOGGER.debug(f"Token expires at: {exp_time} UTC")
            return False
        else:
            _LOGGER.debug(f"Token expired on: {exp_time} UTC")
            return True
        
    async def prepare(self):
        """Prepare the token for use.
        
        Check the token and refresh the token if necessary.
        
        Returns
        -------
        None.

        """
        _LOGGER.debug(f"Preparing token: {self._token}")
        if not self._token:
            _LOGGER.debug("Found empty token - Populating token")
            if self._cache_token and self._token_store_data:
                _LOGGER.debug("Populating from token cache")   
                if not await self._init_from_token_store():
                    _LOGGER.debug("Fetching new token from Enlighten")
                    await self.refresh()
            else:
                _LOGGER.debug("Fetching new token from Enlighten")
                await self.refresh()    
        if self.is_populated:
            _LOGGER.debug(f"Token is populated: {self._token}")
            if self.is_expired:
                if self._auto_renewal:
                    _LOGGER.debug("Found Expired token - Retrieving new token")
                    await self.refresh() 
                else:
                    _LOGGER.debug(
                        """Found Expired token. 
                        Please renew the token or provide the  
                        necessary credentials required for 
                        automatic token renewal"""
                    )

    async def refresh(self):
        """Refresh the Enphase token.
        
        Fetch a new Token from Enlighten, decode the token and set the
        instance's variables accordingly.
        
        Returns
        -------
        None.

        """
        _LOGGER.debug("Refreshing Enphase Token")
        token_raw = await self._fetch_enphase_token()
        decoded = await self._decode_token(token_raw)
        self._token = token_raw
        self._type = decoded["enphaseUser"]
        self.expiration_date = datetime.fromtimestamp(
            decoded["exp"], tz=timezone.utc
        )
        _LOGGER.debug(
            f"New Enphase {self._type} token valid until: {self.expiration_date}"
        )
        try:
            await self.refresh_cookies()
        except httpx.HTTPError:
            pass
        else:
            await self._token_refreshed(token_raw)
    
    async def refresh_cookies(self):
        """Refresh the cookies.
        
        Refresh self._cookies with the cookies returned by 
        self._refresh_token_cookies.

        Returns
        -------
        bool
            True if refreshing the cookies was sucessfull. False otherwise.

        """
        try:
            cookies = await self._refresh_token_cookies(self._token)
        except httpx.HTTPError:
            return False
        else:
            if cookies:
                self._cookies = cookies
                return True
            else:
                return False
    
    async def _init_from_token_store(self):
        """Initialize EnphaseToken from the token cache.
        
        Returns
        -------
        bool
            True if sucessfully initialized from the cache. False otherwise.

        """
        if token_raw := self._token_store_data.get("EnphaseToken"):
            _LOGGER.debug(f"Loaded token from cache: {token_raw}")
            try:
                _LOGGER.debug(
                    f"Initializing using token_raw from the cache: {token_raw}"
                )
                await self._init_from_token_raw(token_raw)
            except httpx.HTTPError:
                return False
            except jwt.exceptions.InvalidTokenError:
                return False
            except InvalidEnphaseToken:
                return False
            else:
                return True
        else:
            _LOGGER.debug("Could not load token from cache")
            return False
    
    async def _init_from_token_raw(self, token_raw):
        """Initialize from a raw token.
        
        Decode and check the token to validate it's integrity and validity.
        
        Parameters
        ----------
        token_raw : str
            Enphase token.

        Raises
        ------
        TokenError
            Can be used to catch an invalid token provided by the user.

        Returns
        -------
        None.

        """
        _LOGGER.debug(f"Initialize using raw token: {token_raw}")
        try:
            decoded = await self._decode_token(token_raw)
            cookies = await self._refresh_token_cookies(token_raw)
        except httpx.HTTPError as err:
            _LOGGER.debug(f"Error while checking the token: {err}")
            raise err
        except jwt.exceptions.InvalidTokenError as err:
            _LOGGER.debug(f"Error while decoding the token: {err}")
            raise err
        else:
            if cookies:
                self._token = token_raw
                self._cookies = cookies
                self._type = decoded["enphaseUser"]
                self.expiration_date = datetime.fromtimestamp(
                    decoded["exp"], tz=timezone.utc
                )
                _LOGGER.debug(f"Token successfully initialized: {self._token}")
            else:
                _LOGGER.debug("Token is not valid")
                raise InvalidEnphaseToken(f"Token invalid: {token_raw}")
    
    async def _refresh_token_cookies(self, token_raw):
        """Call '/auth/check_jwt' to check if token is valid.
        
        Send a HTTP GET request and parse the response.
        Return the the cookies if the token is valid.
        Return None if the token is not valid.
        
        Parameters
        ----------
        token_raw : str
            Enphase token.
            
        Raises
        ------
        httpx.HTTPError
            HTTP error httpx.HTTP.
        
        Returns
        -------
        cookies : dict or None
            Dict containing cookies if token is valid. None otherwise.

        """
        _LOGGER.debug("Calling '/auth/check_jwt' to check token")
        async_client = httpx.AsyncClient(verify=False, timeout=10.0)
        auth_header = {"Authorization": "Bearer " + token_raw}
        url = ENDPOINT_URL_CHECK_JWT.format(self.host)
        try:
            resp = await async_get(url, async_client, headers=auth_header)
        except httpx.HTTPError as err:
            _LOGGER.debug(f"Error while checking token: {err}")
            raise err
        else:
            soup = BeautifulSoup(resp.text, features="html.parser")
            validity = soup.find("h2").contents[0]
            if validity == "Valid token":
                _LOGGER.debug("Token is valid")
                return resp.cookies
            else:
                _LOGGER.debug("Token is not valid")
                return None

    async def _decode_token(self, token_raw):
        """Decode the JWT Enphase token.
        
        Parameters
        ----------
        token_raw : str
            Plain Enphase token.

        Raises
        ------
        err : jwt.exceptions.InvalidTokenError
            Token decoding error.

        Returns
        -------
        decoded : dict
            Dict containing values from the decoded Token.

        """
        _LOGGER.debug(f"Decoding the Enphase token: {token_raw}")
        try:
            decoded = jwt.decode(
                token_raw,
                algorithms=["ES256"],
                options={"verify_signature": False},
            )
        except jwt.exceptions.InvalidTokenError as err:
            _LOGGER.debug(f"Decoding of the Enphase token failed: {token_raw}")
            raise err
        else:
            return decoded

    async def _fetch_enphase_token(self):
        """Fetch the Enphase token from Enlighten.
        
        Returns
        -------
        token_raw : str
            Plain Enphase token.

        """
        _LOGGER.debug("Fetching new token from Enlighten.")
        payload = {
            'user[email]': self.enlighten_username, 
            'user[password]': self.enlighten_password
        }
        try:
            resp = await self._async_post(ENLIGHTEN_LOGIN_URL, data=payload)
        except httpx.HTTPStatusError as err:
            status_code = err.response.status_code
            if status_code == 401:
                raise EnlightenUnauthorized("Enlighten unauthorized") from err
            raise err
        response_data = json.loads(resp.text)
        payload = {
            'session_id': response_data['session_id'],
            'serial_num': self.gateway_serial_num,
            'username': self.enlighten_username
        }
        response = await self._async_post(ENLIGHTEN_TOKEN_URL, json=payload)
        return response.text

    async def _async_post(self, url, **kwargs):
        """Send a HTTP POST request using httpx.
        
        Parameters
        ----------
        url : str
            Target url.
        **kwargs : dict, optional
            Extra arguments for httpx.client.post(**kwargs).

        Returns
        -------
        resp : HTTP response
            httpx response object.

        """
        async_client = httpx.AsyncClient(verify=True, timeout=10.0)
        try:
            resp = await async_post(url, async_client, **kwargs)
        except httpx.HTTPStatusError as err:
            status_code = err.response.status_code
            _LOGGER.debug(
                f"Received status_code {status_code} from Gateway"
            )
            raise err
        else:
            return resp

    async def _token_refreshed(self, token_raw):
        """Cleanup Action for refreshed token."""
        if self._cache_token and self._token_store_data:
            self._token_store_data["EnphaseToken"] = token_raw
            await self.token_store.async_save(self._token_store_data)
        if self._expose_token:
            pass
        
    # async def _load_token_from_cache(self):
    #     """Return the raw token from the cache.

    #     Returns
    #     -------
    #     str or None
    #         Returns the raw token or None.

    #     """
    #     if filepath := self._token_cache_filepath.is_file():
    #         with filepath.open() as f:
    #             token_json = json.load(f)
    #             return token_json.get("EnphaseToken", None)
    #     else:
    #         _LOGGER.debug("Error while checking Path token_cache_filepath")
    #         return None

    # async def _save_token_to_cache(self, token_raw):
    #     """Save the raw token to the cache.
        
    #     Parameters
    #     ----------
    #     token_raw : str
    #         Enphase token.

    #     Returns
    #     -------
    #     None.

    #     """
    #     token_json = {"EnphaseToken": token_raw}
    #     filepath = self._token_cache_filepath
    #     with filepath.open("w+") as f:
    #         json.dump(token_json, f)
        
