"""Enphase Gateway authentication methods."""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from abc import abstractmethod, abstractproperty

import jwt
import httpx
import orjson
from bs4 import BeautifulSoup

from .http import async_get, async_post
from .exceptions import EnlightenUnauthorized, TokenAuthConfigError



_LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


class GatewayAuth:
    """Base class for gateway authentication."""
    
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    async def prepare(self, client: httpx.AsyncClient) -> None:
        """Prepare for authentication."""
    
    @abstractproperty
    def protocol(self) -> str:
        """Return the http protocol."""
    
    @abstractproperty
    def auth(self) -> httpx.DigestAuth | None:
        """Return the httpx auth object."""

    @abstractproperty
    def headers(self) -> dict[str, str]:
        """Return the auth headers."""

    @abstractproperty
    def cookies(self) -> dict[str, str]:
        """Return the cookies."""

    @abstractmethod
    def get_endpoint_url(self, endpoint: str) -> str:
        """Return the URL for the endpoint."""
    

class LegacyAuth(GatewayAuth):
    """Class for legacy authentication using username and password."""
    
    def __init__(self, host: str, username: str, password: str) -> None:
        self.host = host
        self.username = username
        self.password = password
    
    @property
    def protocol(self) -> str:
        """Return http protocol."""
        return "http"
    
    @property
    def auth(self) -> httpx.DigestAuth:
        """Return httpx authentication."""
        if not self.local_username or not self.local_password:
            return None
        return httpx.DigestAuth(self.local_username, self.local_password)
    
    @property
    def headers(self) -> dict[str, str]:
        """Return the headers for legacy authentication."""
        return {}
    
    @property
    def cookies(self) -> dict[str, str]:
        """Return the cookies for legacy authentication."""
        return {}
    
    async def prepare(self, client: httpx.AsyncClient) -> None:
        """Set up authentication method."""
        pass # No setup required
    
    def get_endpoint_url(self, endpoint: str) -> str:
        """Return the URL for the endpoint."""
        return f"http://{self.host}{endpoint}"
    
    
class EnphaseTokenAuth(GatewayAuth):
    """Class for Enphase Token authentication."""
    
    STALE_TOKEN_THRESHOLD = timedelta(days=30)
    
    ENDPOINT_URL_CHECK_JWT = "https://{}/auth/check_jwt"
    LOGIN_URL = "https://enlighten.enphaseenergy.com/login/login.json?"
    TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"
    
    def __init__(
            self,
            host: str,
            enlighten_username: str | None = None,
            enlighten_password: str | None = None,
            gateway_serial_num: str | None = None,
            token_raw: str | None = None,
            cache_token: bool = False,
            cache_path: str | None = None,
            auto_renewal: bool = True,
    ) -> None:
        """Initialize EnphaseToken."""
        self.host = host
        self.enlighten_username = enlighten_username
        self.enlighten_password = enlighten_password
        self.gateway_serial_num = gateway_serial_num
        self._cache_token = cache_token if not token_raw else False
        self._token = token_raw
        self._cookies = None
        
        if self._cache_token:
            if cache_path:
                self._cache_path = Path(cache_path).resolve()
            else:
                self._cache_path = BASE_DIR.joinpath("token.json")
            
        if (enlighten_username and enlighten_password and gateway_serial_num):
            self._auto_renewal = auto_renewal
        elif token_raw:
            self._auto_renewal = False
        else:
            raise TokenAuthConfigError(
                "Invalid combination of arguments provided. "
                + "Please provide Enlighten credentials or an Enphase token." 
            )

    @property
    def protocol(self) -> str:
        """Return http protocol."""
        return "https"

    @property
    def auth(self) -> None:
        """Return httpx authentication."""
        return None # No auth required for token authentication
    
    @property
    def token(self) -> str:
        """Return the Enphase token."""
        return self._token
    
    @property
    def expiration_date(self) -> datetime:
        """Return the expiration date of the Enphase token."""
        payload = self._decode_token()
        return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Return the expiration status of the Enphase token."""
        exp_time = self.expiration_date - self.STALE_TOKEN_THRESHOLD
        if datetime.now(tz=timezone.utc) <= exp_time:
            _LOGGER.debug(f"Token expires at: {exp_time} UTC")
            return False
        else:
            _LOGGER.debug(f"Token expired on: {exp_time} UTC")
            return True
    
    @property
    def headers(self) -> None:
        """Return the headers for token authentication."""
        return {"Authorization": f"Bearer {self.token}"}
    
    @property
    def cookies(self) -> dict[str, str]:
        """Return the cookies for token authentication."""
        return self._cookies 
    
    def get_endpoint_url(self, endpoint: str) -> str:
        """Return the URL for the endpoint."""
        return f"https://{self.host}{endpoint}"
    
    async def prepare(self, client: httpx.AsyncClient) -> None:
        """Set up token for token authentication."""
        if not self._token:
            if self._cache_token:
                # load token from cache
                pass
            else:
                await self.refresh()
    
        else:
            _LOGGER.debug(f"Token is populated: {self.token}")
            if self.is_expired:
                if self._auto_renewal:
                    _LOGGER.debug("Found Expired token - Retrieving new token")
                    await self.refresh()
                else:
                    _LOGGER.debug(
                        """Found Expired token. 
                        Please renew the token or enable token auto renewal 
                        and provide the necessary credentials required for 
                        automatic token renewal"""
                    )
            elif not self.cookies:
                await self.refresh_cookies()
    
    async def refresh(self) -> None:
        """Refresh the Enphase token."""
        _LOGGER.debug("Refreshing Enphase token")
        
        if not self.enlighten_username or not self.enlighten_password:
            pass
        
        if not self.gateway_serial_num:
            pass
        
        self._token = await self._fetch_enphase_token()
        _LOGGER.debug(f"New Enphase token valid until: {self.expiration_date}")
        # TODO: Add logic if token could not be retrieved
        try:
            _cookies = await self._check_jwt()
        except httpx.HTTPError:
            pass
        else:
            if _cookies:
                self._cookies = _cookies
                await self._token_refreshed()
    
    async def refresh_cookies(self) -> bool:
        """Refresh the cookies."""
        try:
            cookies = await self._check_jwt()
        except httpx.HTTPError:
            return False
        else:
            if cookies:
                self._cookies = cookies
                return True
            else:
                return False
        
    async def _fetch_enphase_token(self) -> str:
        """Fetch the Enphase token from Enlighten."""
        _LOGGER.debug("Fetching new token from Enlighten.")
        _async_client = httpx.AsyncClient(verify=True, timeout=10.0)
        async with _async_client as async_client:
            # retrieve session id from enlighten
            resp = await self._async_post_enlighten(
                async_client,
                self.LOGIN_URL,
                data={
                    'user[email]': self.enlighten_username, 
                    'user[password]': self.enlighten_password
                }
            )
            response_data = orjson.loads(resp.text)
            self._is_consumer = response_data["is_consumer"]
            self._manager_token = response_data["manager_token"]
            
            # retrieve token from enlighten
            resp = await self._async_post_enlighten(
                async_client,
                self.TOKEN_URL,
                json={
                    'session_id': response_data['session_id'],
                    'serial_num': self.gateway_serial_num,
                    'username': self.enlighten_username
                }
            )
            return resp.text
    
    async def _async_post_enlighten(
        self,
        async_client: httpx.AsyncClient,
        url: str,
        **kwargs
        ) -> httpx.Response:
        """Send a HTTP POST request to Enlighten."""
        try:
            resp = await async_post(async_client, url, **kwargs)
        
        except httpx.HTTPStatusError as err:
            status_code = err.response.status_code
            _LOGGER.debug(
                f"Received status_code {status_code} from Gateway"
            )
            if status_code == 401:
                raise EnlightenUnauthorized(
                    "Enlighten unauthorized",
                    request=err.request,
                    response=err.response
                )
            raise err
        
        else:
            return resp
    
    def _decode_token(self) -> dict:
        """Decode the JWT Enphase token."""
        try:
            jwt_payload = jwt.decode(
                self._token,
                algorithms=["ES256"],
                options={"verify_signature": False},
            )
        except jwt.exceptions.InvalidTokenError as err:
            _LOGGER.debug(f"Decoding of the Enphase token failed: {self._token}")
            raise err
        else:
            return jwt_payload
    
    async def _check_jwt(
        self,
        async_client: httpx.AsyncClient | None = None,
    ) -> httpx.Cookies | None:
        """Call '/auth/check_jwt' to check if token is valid.
        
        Return cookies if the token is valid return None otherwise.
        
        """
        _LOGGER.debug("Calling '/auth/check_jwt' to check token")
        if not async_client:
            async_client = httpx.AsyncClient(verify=False, timeout=10.0)
        try:
            resp = await async_get(
                async_client,
                f"https://{self.host}/auth/check_jwt",
                headers = {"Authorization": f"Bearer {self.token}"},
            )
        except httpx.HTTPError as err:
            _LOGGER.debug(f"Error while checking token: {err}")
            raise err
        else:
            soup = BeautifulSoup(resp.text, features="html.parser")
            validity = soup.find("h2").contents[0]
            if validity == "Valid token.":
                _LOGGER.debug("Token is valid")
                return resp.cookies
            else:
                _LOGGER.debug("Token is not valid")
                return None    
    
    async def _token_refreshed(self):
        """Cleanup Action for refreshed token."""
        if self._cache_token:
            self._save_token_to_cache(self.token)
 
    async def _load_token_from_cache(self):
        """Return the raw token from the cache.

        Returns
        -------
        str or None
            Returns the raw token or None.

        """
        if filepath := self._token_cache_filepath.is_file():
            with filepath.open() as f:
                token_json = json.load(f)
                return token_json.get("EnphaseToken", None)
        else:
            _LOGGER.debug("Error while checking Path token_cache_filepath")
            return None

    async def _save_token_to_cache(self, token_raw):
        """Save the raw token to the cache.
        
        Parameters
        ----------
        token_raw : str
            Enphase token.

        Returns
        -------
        None.

        """
        token_json = {"EnphaseToken": token_raw}
        filepath = self._token_cache_filepath
        with filepath.open("w+") as f:
            json.dump(token_json, f)
    
