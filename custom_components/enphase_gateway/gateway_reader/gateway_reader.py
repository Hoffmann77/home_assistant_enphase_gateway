"""Read parameters from an Enphase(R) gateway on your local network."""

import logging
from collections.abc import Iterable

import httpx
from awesomeversion import AwesomeVersion
from envoy_utils.envoy_utils import EnvoyUtils

from .http import async_get
from .endpoint import GatewayEndpoint
from .utils import is_ipv6_address
from .gateway import EnvoyLegacy, Envoy, EnvoyS, EnvoySMetered
from .const import LEGACY_ENVOY_VERSION
from .gateway_info import GatewayInfo
from .auth import LegacyAuth, EnphaseTokenAuth
from .exceptions import GatewayAuthenticationRequired, GatewaySetupError


_LOGGER = logging.getLogger(__name__)


class GatewayReader:
    """Class to retrieve data from an Enphase gateway.

    Parameters
    ----------
    host : str
        Hostname of the Gateway.
    async_client : httpx.AsyncClient, optional
        httpx async client. A client will be created if no client is provided.

    Attributes
    ----------
    host : str
        Hostname of the Gateway.
    auth : {LegacyAuth, EnphaseTokenAuth}
        Gateway authentication class.
    gateway : Gateway class.
        Gateway class used to access gateway data.

    """

    def __init__(
            self,
            host: str,
            async_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize instance of GatewayReader."""
        self.host = host.lower()
        if is_ipv6_address(self.host):
            self.host = f"[{self.host}]"
        self.auth = None
        self.gateway = None
        self._async_client = async_client or self._get_async_client()
        self._info = GatewayInfo(self.host, self._async_client)

    @property
    def name(self) -> str | None:
        """Return the verbose name of the gateway."""
        if self.gateway:
            return self.gateway.VERBOSE_NAME
        return "Enphase Gateway"

    @property
    def serial_number(self) -> str | None:
        """Return the gateway's serial number."""
        return self._info.serial_number

    @property
    def part_number(self) -> str | None:
        """Return the gateway's part number."""
        return self._info.part_number

    @property
    def firmware_version(self) -> AwesomeVersion:
        """Return the gateway's firmware version."""
        return self._info.firmware_version

    @property
    def is_ready(self) -> bool:
        """Return the setup status of the gateway."""
        if self._info.populated and self.auth and self.gateway:
            return True
        return False

    async def prepare(self):
        """Prepare the gateway reader.

        Update the gateway info and detect the gateway model.

        """
        await self._info.update()
        await self._detect_model()
        _LOGGER.debug(
            "Gateway info: "
            + f"part_number: {self._info.part_number}, "
            + f"firmware_version: {self._info.firmware_version}, "
            + f"imeter: {self._info.imeter}, "
            + f"web_tokens: {self._info.web_tokens}"
        )
        _LOGGER.debug(
            f"Initial Gateway class: {self.gateway.__class__.__name__}"
        )

    async def update(
        self,
        limit_endpoints: Iterable[str] | None = None
    ) -> None:
        """Update the gateway reader."""
        await self._info.update()
        await self.auth.update(self._async_client)
        await self.update_endpoints(limit_endpoints=limit_endpoints)

        if self.gateway.initial_update_finished is False:
            self.gateway.run_probes()
            if subclass := self.gateway.get_subclass():
                self.gateway = subclass
                await self.update_endpoints(
                    limit_endpoints=limit_endpoints,
                    force_update=True,
                )

            _LOGGER.debug(f"Gateway class: {self.gateway.__class__.__name__}")
            self.gateway.initial_update_finished = True

    async def authenticate(
        self,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
        cache_token: bool = False,
        cache_path: str | None = None,
        auto_renewal: bool = True,
    ) -> None:
        """Authenticate to the Enphase gateway based on firmware version."""
        if not self._info.populated:
            raise GatewaySetupError(
                "Gateway info missing. Please make sure to call 'prepare()' "
                + "before you authenticate"
            )

        if self._info.web_tokens:
            _LOGGER.debug("Using EnphaseTokenAuth for authentication.")
            if token or (username and password):
                self.auth = EnphaseTokenAuth(
                    self.host,
                    enlighten_username=username,
                    enlighten_password=password,
                    gateway_serial_num=self._info.serial_number,
                    token_raw=token,
                    cache_token=cache_token,
                    cache_filepath=cache_path,
                    auto_renewal=auto_renewal,
                )
        else:
            _LOGGER.debug("Using envoy/installer authentication.")
            if not username or username == "installer":
                username = "installer"  # FIXME: fix legacy auth
                password = EnvoyUtils.get_password(
                    self._info.serial_number,
                    username
                )
            elif username == "envoy" and not password:
                password = self._info.serial_number[:6]
            elif username and password:
                self.auth = LegacyAuth(
                    self.host,
                    username,
                    self._info.serial_number
                )
        _LOGGER.debug(
            f"Using authentication class: {self.auth.__class__.__name__}"
        )
        if not self.auth:
            _LOGGER.error(
                "You must include username/password or a token"
                " to authenticate to the Envoy."
            )
            raise GatewayAuthenticationRequired(
                "Could not setup an authentication method."
            )

        await self.auth.update(self._async_client)

    async def _detect_model(self) -> None:
        """Detect the Enphase gateway model.

        Detect gateway model based on info.xml parmeters.

        """
        if self.firmware_version < LEGACY_ENVOY_VERSION:
            self.gateway = EnvoyLegacy()
        elif self._info.imeter and self._info.imeter == "true":
            self.gateway = EnvoySMetered()
        elif self._info.imeter and self._info.imeter == "false":
            self.gateway = EnvoyS()
        else:
            self.gateway = Envoy()

    def _get_async_client(self) -> httpx.AsyncClient:
        """Return default httpx client."""
        return httpx.AsyncClient(
            verify=False,
            timeout=10
        )

    async def update_endpoints(
            self,
            limit_endpoints: Iterable[str] | None = None,
            force_update: bool = False,
    ) -> None:
        """Update endpoints."""
        endpoints = self.gateway.required_endpoints
        _LOGGER.debug(f"Updating endpoints: {endpoints}")
        for endpoint in endpoints:
            # TODO: fix below line breaking integration
            # if limit_endpoints and endpoint.path not in limit_endpoints:
            #     continue
            if endpoint.update_required or force_update is True:
                await self._update_endpoint(endpoint)
                endpoint.success()

    async def _update_endpoint(self, endpoint: GatewayEndpoint) -> None:
        """Fetch a single endpoint and store the response."""
        formatted_url = endpoint.get_url(self.auth.protocol, self.host)
        response = await self._async_get(
            formatted_url,
            follow_redirects=False
        )
        if self.gateway:
            self.gateway.set_endpoint_data(endpoint, response)

    async def _async_get(self, url: str, handle_401: bool = True, **kwargs):
        """Make a HTTP GET request to the gateway."""
        try:
            resp = await async_get(
                self._async_client,
                url,
                headers=self.auth.headers,
                cookies=self.auth.cookies,
                auth=self.auth.auth,
                **kwargs
            )
        except httpx.HTTPStatusError as err:
            _LOGGER.debug(
                f"Gateway returned status code: {err.response.status_code}"
            )
            if err.response.status_code == 401 and handle_401:
                _LOGGER.debug("Trying to resolve 401 error")
                self.auth.resolve_401(self._async_client)
                return await self._async_get(
                    url,
                    handle_401=False,
                    **kwargs
                )
            else:
                raise err

        else:
            return resp
