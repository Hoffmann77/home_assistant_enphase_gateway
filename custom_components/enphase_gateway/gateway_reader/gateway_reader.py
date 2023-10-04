"""Read parameters from an Enphase(R) gateway on the local network."""

import logging
from collections.abc import Iterable

import httpx
from awesomeversion import AwesomeVersion
from envoy_utils.envoy_utils import EnvoyUtils
from homeassistant.util.network import is_ipv6_address

from .http import async_get
from .endpoint import GatewayEndpoint
from .gateway import EnvoyLegacy, Envoy, EnvoyS, EnvoySMetered
from .const import LEGACY_ENVOY_VERSION
from .gateway_info import GatewayInfo
from .auth import LegacyAuth, EnphaseTokenAuth
from .exceptions import GatewayAuthenticationRequired


_LOGGER = logging.getLogger(__name__)


class GatewayReader:
    """Instance of EnvoyReader."""

    MESSAGES = {
        "daily_production_not_available":
            "Daily production data not available for your Envoy device.",
        "seven_day_production_not_available":
            "Seven day production data not available for your Envoy device.",
        "battery_not_available":
            "Battery storage data not available for your Envoy device.",
        "consumption_not_available":
            "Consumption data not available for your Envoy device.",
        "grid_status_not_available":
            "Grid status not available for your Envoy device.",
    }

    def __init__(
            self,
            host: str,
            # username: str | None = None,
            # password: str | None = None,
            # token: str | None = None,
            async_client: httpx.AsyncClient | None = None,
            get_inverters=False,
    ) -> None:
        """Initialize instance of EnvoyReader."""
        self.host = host.lower()
        if is_ipv6_address(self.host):
            self.host = f"[{self.host}]"
        self.auth = None
        self._async_client = async_client or self._get_async_client()
        self._info = GatewayInfo(self.host, self._async_client)
        # self._username = username
        # self._password = password
        # self._token = token
        # self.endpoint_results = {}
        # self.storages = {}
        self.gateway = None
        # self.get_inverters = get_inverters

    @property
    def name(self) -> str | None:
        """Return the verbose name of the gateway."""
        if self.gateway:
            return self.gateway.VERBOSE_NAME
        return "Enphase Gateway"

    @property
    def serial_number(self) -> str | None:
        """Return the Envoy serial number."""
        return self._info.serial_number

    @property
    def part_number(self) -> str | None:
        """Return the Envoy part number."""
        return self._info.part_number

    @property
    def firmware_version(self) -> AwesomeVersion:
        """Return the Envoy firmware version."""
        return self._info.firmware_version

    @property
    def is_ready(self) -> bool:
        """Return the status."""
        if self._info.setup_complete and self.auth and self.gateway:
            return True
        return False

    @property
    def all_values(self):
        """Return all values of the gateway."""
        def iter():
            for key, val in self.gateway.all_values.items():
                yield key, val

        return dict(iter())

    async def prepare(self):
        """Prepare the gateway reader."""
        await self._info.update()
        await self._detect_model()
        _LOGGER.debug(
            "Gateway info: "
            + f"part_number: {self._info.part_number}, "
            + f"firmware_version: {self._info.firmware_version}, "
            + f"imeter: {self._info.imeter}, "
            + f"web_tokens: {self._info.web_tokens}"
        )
        _LOGGER.debug(f"Initial Gateway class: {self.gateway.__class__}")

    async def update(
        self,
        limit_endpoints: Iterable[str] | None = None
    ) -> None:
        """Fetch endpoints and update data."""
        await self._info.update()
        await self.auth.prepare(self._async_client)
        await self.update_endpoints(limit_endpoints=limit_endpoints)

        if self.gateway.initial_update_finished is False:
            self.gateway.run_probes()
            if subclass := self.gateway.get_subclass():
                self.gateway = subclass
                await self.update_endpoints(limit_endpoints=limit_endpoints)

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
            return  # TODO add logic

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
                username = "installer"
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

        await self.auth.prepare(self._async_client)

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
            _LOGGER.debug(f"Setting endpoint data: {endpoint} : {response}")
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

#     def run_in_console(self):
#         """If running this module directly, print all the values in the console."""
#         print("Reading...")
#         loop = asyncio.get_event_loop()
#         data_results = loop.run_until_complete(
#             asyncio.gather(self.getData(), return_exceptions=False)
#         )

#         loop = asyncio.get_event_loop()
#         results = loop.run_until_complete(
#             asyncio.gather(
#                 self.production(),
#                 self.consumption(),
#                 self.daily_production(),
#                 self.daily_consumption(),
#                 self.seven_days_production(),
#                 self.seven_days_consumption(),
#                 self.lifetime_production(),
#                 self.lifetime_consumption(),
#                 self.inverters_production(),
#                 self.battery_storage(),
#                 return_exceptions=False,
#             )
#         )

#         print(f"production:              {results[0]}")
#         print(f"consumption:             {results[1]}")
#         print(f"daily_production:        {results[2]}")
#         print(f"daily_consumption:       {results[3]}")
#         print(f"seven_days_production:   {results[4]}")
#         print(f"seven_days_consumption:  {results[5]}")
#         print(f"lifetime_production:     {results[6]}")
#         print(f"lifetime_consumption:    {results[7]}")
#         if "401" in str(data_results):
#             print(
#                 "inverters_production:    Unable to retrieve inverter data - Authentication failure"
#             )
#         elif results[8] is None:
#             print(
#                 "inverters_production:    Inverter data not available for your Envoy device."
#             )
#         else:
#             print(f"inverters_production:    {results[8]}")
#         print(f"battery_storage:         {results[9]}")


# if __name__ == "__main__":

#     TESTREADER = GatewayReader(
#         "192.168.178.",
#         username="envoy",
#         password="",
#         gateway_serial_num=None,
#         use_token_auth=False,
#         token_raw=None,
#         use_token_cache=False,
#         token_cache_filepath=None,
#         single_inverter_entities=False,
#         inverters=False,
#         async_client=None,
#     )

#     TESTREADER.run_in_console()
