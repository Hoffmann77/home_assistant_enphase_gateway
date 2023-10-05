"""Enphase Gateway authentication module."""

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
from .exceptions import (
    EnlightenAuthenticationError,
    EnlightenCommunicationError,
    GatewayAuthenticationError,
    GatewayCommunicationError,
    InvalidTokenError,
    TokenAuthConfigError,
    TokenRetrievalError,
)


_LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


class GatewayAuth:
    """Base class for gateway authentication."""

    def __init__(self) -> None:
        """Initialize GatewayAuth."""
        pass

    @abstractmethod
    async def update(self, client: httpx.AsyncClient) -> None:
        """Update the authentication class for authentication."""

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
        self._host = host
        self._username = username
        self._password = password

    @property
    def protocol(self) -> str:
        """Return http protocol."""
        return "http"

    @property
    def auth(self) -> httpx.DigestAuth:
        """Return httpx authentication."""
        if not self._username or not self._password:
            return None
        return httpx.DigestAuth(self._username, self._password)

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers for legacy authentication."""
        return {}

    @property
    def cookies(self) -> dict[str, str]:
        """Return the cookies for legacy authentication."""
        return {}

    async def update(self, client: httpx.AsyncClient) -> None:
        """Update authentication method."""
        pass  # No setup required

    async def resolve_401(self, async_client):
        """Resolve a 401 Unauthorized response."""
        pass

    def get_endpoint_url(self, endpoint: str) -> str:
        """Return the URL for the endpoint."""
        return f"http://{self._host}{endpoint}"


class EnphaseTokenAuth(GatewayAuth):
    """Class used for Enphase token authentication.

    Parameters
    ----------
    host : str
        Gateway host ip-adress.
    enlighten_username : str, optional
        Enlighten login username.
    enlighten_password : str, optional
        Enlighten login password.
    gateway_serial_num : str, optional
        Gateway serial number.
    token_raw : str, optional
        Enphase token.
    cache_token : bool, default=False
        Cache the token.
    cache_filepath : str, default="token.json"
        Cache filepath.
    auto_renewal : bool, default=True,
        Auto renewal of the token. Defaults to False if the arguments
        'enlighten_username', 'enlighten_password' and 'gateway_serial_num'
        are not provided.
    stale_token_threshold : datetime.timedelta, default=timedelta(days=30)
        Timedelta describing the stale token treshold.

    Raises
    ------
    TokenAuthConfigError
        If token authentication is not set up correcty.
    TokenRetrievalError
        If a token could not be retrieved from the Enlighten cloud.
    InvalidTokenError
        If a token is not valid.
    GatewayAuthenticationError
        If gateway authentication could not be set up.
    EnlightenAuthenticationError
        If Enlighten cloud credentials are not valid.

    """

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
            cache_filepath: str | None = "token.json",
            auto_renewal: bool = True,
            stale_token_threshold: timedelta = timedelta(days=30)
    ) -> None:
        """Initialize EnphaseTokenAuth."""
        self._host = host
        self._enlighten_username = enlighten_username
        self._enlighten_password = enlighten_password
        self._gateway_serial_num = gateway_serial_num
        self._token = token_raw
        self._cache_token = cache_token
        self._cache_filepath = cache_filepath
        self._stale_token_threshold = stale_token_threshold
        self._enlighten_credentials = False
        self._cookies = None

        if self._cache_filepath:
            self._cache_filepath = Path(self._cache_filepath).resolve()

        if enlighten_username and enlighten_password and gateway_serial_num:
            self._enlighten_credentials = True
            self._auto_renewal = auto_renewal
        elif not token_raw:
            raise TokenAuthConfigError(
                "Invalid combination of optional arguments. "
                + "Please provide the arguments 'enlighten_username', "
                + "'enlighten_password' and 'gateway_serial_num' or "
                + "the argument 'token_raw'."
            )
        else:
            self._auto_renewal = False

    @property
    def protocol(self) -> str:
        """Return http protocol."""
        return "https"

    @property
    def auth(self) -> None:
        """Return httpx authentication."""
        return None  # No auth required for token authentication

    @property
    def token(self) -> str | None:
        """Return the Enphase token."""
        return self._token

    @property
    def headers(self) -> None:
        """Return the headers for token authentication."""
        return {"Authorization": f"Bearer {self.token}"}

    @property
    def cookies(self) -> dict[str, str]:
        """Return the cookies for token authentication."""
        return self._cookies

    @property
    def expiration_date(self) -> datetime:
        """Return the expiration date of the Enphase token."""
        payload = self._decode_token(self._token)
        return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Return the expiration status of the Enphase token."""
        if datetime.now(tz=timezone.utc) <= self.expiration_date:
            return False
        return True

    @property
    def is_stale(self) -> bool:
        """Return whether the token is about to expire."""
        exp_time = self.expiration_date - self._stale_token_threshold
        if datetime.now(tz=timezone.utc) <= exp_time:
            return False
        return True

    def get_endpoint_url(self, endpoint: str) -> str:
        """Return the URL for the endpoint."""
        return f"https://{self._host}{endpoint}"

    async def update(self, async_client: httpx.AsyncClient) -> None:
        """Update authentication method."""
        if not self._token:
            _LOGGER.debug(
                "Token not found - setting up token for authentication"
            )
            await self._setup_token(async_client)

        if self.is_stale:
            if self._auto_renewal:
                try:
                    _LOGGER.debug("Stale token - trying to refresh token")
                    await self.refresh_token()
                except httpx.TransportError as err:
                    if self.is_expired:
                        raise err
                    else:
                        _LOGGER.debug("Error refreshing stale token: {err}")
                        pass

            else:
                _LOGGER.warning(
                    "The Enphase token you provided is about to expire. "
                    + "Please provide a new token."
                )

        if not self.cookies:
            _LOGGER.debug(
                "Cookies not found - refreshing cookies"
            )
            await self.refresh_cookies(async_client)

    async def refresh_token(self) -> None:
        """Refresh the Enphase token."""
        if not self._enlighten_credentials:
            raise TokenAuthConfigError(
                "Enlighten credentials required for token refreshing"
            )
        self._token = await self._fetch_enphase_token()
        self._cookies = None
        _LOGGER.debug(f"New token valid until: {self.expiration_date}")

    async def refresh_cookies(self, async_client: httpx.AsyncClient) -> None:
        """Try to refresh the cookies."""
        cookies = await self._check_jwt(async_client, self._token)
        if cookies is not None:
            self._cookies = cookies

    async def resolve_401(self, async_client) -> bool:
        """Resolve 401 Unauthorized response."""
        try:
            self.refresh_cookies(async_client)
        except httpx.TransportError as err:
            raise GatewayCommunicationError(
                "Error trying to refresh token cookies: {err}",
                request=err.request,
            ) from err
        except InvalidTokenError:
            self._token = None
            self._cookies = None
            self.update(async_client)

    async def _setup_token(self, async_client: httpx.AsyncClient) -> None:
        """Set up the initial Enphase token."""
        if self._cache_token:
            token = await self._load_token_from_cache()
            cookies = await self._check_jwt(
                async_client,
                token,
                fail_silent=True
            )
            if token and cookies:
                self._token = token
                self._cookies = cookies

        if not self._token:
            try:
                token = await self._fetch_enphase_token()
            except httpx.TransportError as err:
                raise err
            except httpx.HTTPError as err:
                raise TokenRetrievalError(
                    "Could not retrieve a new token from Enlighten"
                ) from err
            else:
                self._token = token

        if not self._token:
            raise GatewayAuthenticationError(
                "Could not obtain a token for token authentication"
            )

    def _decode_token(self, token: str) -> dict:
        """Decode the given JWT token."""
        try:
            jwt_payload = jwt.decode(
                token,
                algorithms=["ES256"],
                options={"verify_signature": False},
            )
        except jwt.exceptions.InvalidTokenError as err:
            _LOGGER.debug(f"Error decoding JWT token: {token[:6]}, {err}")
            raise err
        else:
            return jwt_payload

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
                    'user[email]': self._enlighten_username,
                    'user[password]': self._enlighten_password
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
                    'serial_num': self._gateway_serial_num,
                    'username': self._enlighten_username
                }
            )
            return resp.text

    async def _async_post_enlighten(
        self,
        async_client: httpx.AsyncClient,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Send a HTTP POST request to the Enlighten platform."""
        try:
            resp = await async_post(async_client, url, **kwargs)
        except httpx.TransportError as err:
            raise EnlightenCommunicationError(
                "Error communicating with the Enlighten platform",
                request=err.request,
            ) from err
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 401:
                raise EnlightenAuthenticationError(
                    "Invalid Enlighten credentials",
                    request=err.request,
                    response=err.response,
                ) from err
            raise err
        else:
            return resp

    async def _check_jwt(
            self,
            async_client: httpx.AsyncClient,
            token: str,
            fail_silent=False
    ) -> None:
        """Check if the jwt token is valid.

        Call auth/check_jwt to get the token validated by the gateway.
        The endpoint responds:
            - 200 if the token is in the gateway's token db:
                - Returns 'Valid token.' html response and cookie 'sessionId'
                if the token is valid.
            - 401 if token is not in the gateway's token db.
        """
        _LOGGER.debug("Validating token using the 'auth/check_jwt' endpoint.")
        if token is None:
            if fail_silent:
                return None
            raise InvalidTokenError(f"Invalid token: '{token[:9]}...'")

        try:
            resp = await async_get(
                async_client,
                f"https://{self._host}/auth/check_jwt",
                headers={"Authorization": f"Bearer {token}"},
                retries=1,
            )

        except httpx.HTTPStatusError as err:
            if resp.status_code == 401:
                _LOGGER.debug(f"Error while checking token: {err}")
                if fail_silent:
                    return None
                raise InvalidTokenError(
                    f"Invalid token: '{token[:9]}...'"
                ) from err

        except httpx.TransportError as err:
            _LOGGER.debug(f"Transport Error while checking token: {err}")
            if fail_silent:
                return None
            raise GatewayCommunicationError(
                "Error trying to validate token: {err}",
                request=err.request,
            ) from err

        else:
            soup = BeautifulSoup(resp.text, features="html.parser")
            validity = soup.find("h2").contents[0]
            if validity == "Valid token.":
                _LOGGER.debug(f"Valid token: '{token[:9]}...'")
                return resp.cookies
            else:
                _LOGGER.debug(f"Invalid token: '{token[:9]}...'")
                if fail_silent:
                    return None
                raise InvalidTokenError(f"Invalid token: '{token[:9]}...'")

    async def _token_refreshed(self):
        """Signal for refreshed token."""
        if self._cache_token:
            self._save_token_to_cache(self.token)

    async def _load_token_from_cache(self) -> str | None:
        """Return the cached token."""
        if filepath := self._cache_filepath.is_file():
            with filepath.open() as f:
                token_json = json.load(f)
            return token_json.get("EnphaseToken")

        _LOGGER.debug(
            f"Error loading token from cache: {self._cache_filepath}"
        )
        return None

    async def _save_token_to_cache(self, token_raw: str) -> None:
        """Add the token to the cache."""
        token_json = {"EnphaseToken": token_raw}
        filepath = self._cache_filepath
        with filepath.open("w+") as f:
            json.dump(token_json, f)
