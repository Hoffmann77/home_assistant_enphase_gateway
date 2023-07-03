"""Provide the EnphaseToken class for the envoy_reader module."""

import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta

import httpx
import jwt


_LOGGER = logging.getLogger(__name__)

ENLIGHTEN_LOGIN_URL = "https://enlighten.enphaseenergy.com/login/login.json?"
ENLIGHTEN_TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"


class EnphaseToken:
    """Enphase Token."""
    
    def __init__(
            self, 
            enlighten_username,
            enlighten_password,
            gateway_serial_num,
            filepath=None
        ):
        """Initialize EnphaseToken."""
        self.enlighten_username = enlighten_username
        self.enlighten_password = enlighten_password
        self.gateway_serial_num = gateway_serial_num
        self.expiration_date = None
        self._filepath = filepath
        self._token = None
        self._type = None
        self._renewal_buffer = 600
        
    @property
    def token(self):
        """Return the raw token."""
        return self._token        
    
    @property
    def is_valid(self):
        """Return if token is valid.
        
        Returns
        -------
        bool
            If token is valid return True. Otherwise return False.

        """
        if self._token and self.expiration_date:
            delta = timedelta(seconds=self._renewal_buffer) 
            exp_time = self.expiration_date - delta
            if datetime.now(tz=timezone.utc) <= exp_time:
                _LOGGER.debug(f"Token expires at: {exp_time} UTC")
                return True
            else:
                _LOGGER.debug(f"Token expired on: {exp_time} UTC")
                return False
        else:
            return False
        
    async def prepare(self):
        """Check the Enphase token and update token if necessary."""
        _LOGGER.debug(f"Checking Enphase token: {self._token}")
        if not self._token:
            _LOGGER.debug("Found empty token - Retrieving new token")
            await self.update()
        else:
            _LOGGER.debug(f"Token is populated: {self._token}")
            if not self.is_valid:
                _LOGGER.debug("Found Expired token - Retrieving new token")
                await self.update() 
        
    async def update(self):
        """Update the token.
        
        Returns
        -------
        None.

        """
        _LOGGER.debug("Updating Enphase Token.")
        token_raw = await self._fetch_enphase_token()
        decoded = await self._decode_token(token_raw)
        self._token = token_raw
        self._type = decoded["enphaseUser"]
        self.expiration_date = datetime.fromtimestamp(
            decoded["exp"], tz=timezone.utc
        )
        _LOGGER.debug(
            f"New Enphase {self._type} Token valid until: {self.expiration_date}"
        )
        
    async def _decode_token(self, token):
        """Decode the JWT token and return the decoded token dict."""
        try:
            decoded = jwt.decode(
                token,
                algorithms=["ES256"],
                options={"verify_signature": False},
            )
        except jwt.exceptions.InvalidTokenError as err:
            _LOGGER.debug(f"Decoding of Enphase token failed: {token}")
            raise err
        else:
            return decoded

    async def _fetch_enphase_token(self):
        """Fetch the Enphase token from Enlighten."""
        _LOGGER.debug("Fetching new token from Enlighten.")
        payload = {
            'user[email]': self.enlighten_username, 
            'user[password]': self.enlighten_password
        }
        response = await self._async_post(ENLIGHTEN_LOGIN_URL, data=payload)
        response_data = json.loads(response.text)
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
        client = httpx.AsyncClient(verify=False, timeout=10.0)
        async with client:
            for attempt in range(1, 4):
                _LOGGER.debug(f"HTTP POST Attempt #{attempt}: {url}")
                try:
                    resp = await client.post(url, **kwargs)
                    _LOGGER.debug(f"HTTP POST {url}: {resp}: {resp.text}")
                    _LOGGER.debug(f"HTTP POST Cookie: {resp.cookies}")
                    resp.raise_for_status()
                except httpx.HTTPStatusError as err:
                    status_code = err.response.status_code
                    _LOGGER.debug(
                        f"Received status_code {status_code} from Gateway."
                    )
                    raise err
                except httpx.TransportError:
                    if attempt >= 3:
                        raise
                    else:
                        await asyncio.sleep(attempt * 0.15)
                else:
                    return resp