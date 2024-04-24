"""GatewayReader update coordinator."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, TYPE_CHECKING

import httpx
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_TOKEN,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ALLOWED_ENDPOINTS
from .gateway_reader.auth import EnphaseTokenAuth
from .gateway_reader.exceptions import (
    EnlightenAuthenticationError,
    GatewayAuthenticationRequired,
    GatewayAuthenticationError,
)


if TYPE_CHECKING:
    from .gateway_reader import GatewayReader


SCAN_INTERVAL = timedelta(seconds=60)

STORAGE_KEY = "enphase_gateway"
STORAGE_VERSION = 1

TOKEN_REFRESH_CHECK_INTERVAL = timedelta(days=1)
STALE_TOKEN_THRESHOLD = timedelta(days=3).total_seconds()

_LOGGER = logging.getLogger(__name__)


class GatewayReaderUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for gateway reader."""

    def __init__(
            self,
            hass: HomeAssistant,
            reader: GatewayReader,
            entry: ConfigEntry
    ) -> None:
        """Initialize DataUpdateCoordinator for the gateway."""
        self.gateway_reader = reader
        self.entry = entry
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self._setup_complete = False
        self._cancel_token_refresh: CALLBACK_TYPE | None = None
        self._store = Store(
            hass,
            STORAGE_VERSION,
            ".".join([STORAGE_KEY, entry.entry_id]),
        )
        self._store_data = None
        self._store_update_pending = False
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data[CONF_NAME],
            update_interval=SCAN_INTERVAL,
            # always_update=False, # TODO: Added in ha 2023.9
        )

    @staticmethod
    async def async_remove_store(
        cls, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Remove all data from the store."""
        store = Store(
            hass,
            STORAGE_VERSION,
            ".".join([STORAGE_KEY, entry.entry_id]),
        )
        await store.async_remove()

    async def _async_setup_and_authenticate(self) -> None:
        """Set up the gateway reader and authenticate."""
        gateway_reader = self.gateway_reader
        await gateway_reader.prepare()
        if not gateway_reader.serial_number:
            return  # TODO add logic

        if token := await self._async_load_cached_token():
            await gateway_reader.authenticate(
                username=self.username,
                password=self.password,
                token=token,
                cache_token=False,
                auto_renewal=False,
            )
            # TODO check method if applicable
            self._async_refresh_token_if_needed(dt_util.utcnow())
            return

        await self.gateway_reader.authenticate(
            username=self.username,
            password=self.password
        )

        await self._async_update_cached_token()

    @callback
    def _async_refresh_token_if_needed(self, now: datetime) -> None:
        """Proactively refresh token if its stale."""
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return
        if self.gateway_reader.auth.is_stale:
            self.hass.async_create_background_task(
                self._async_try_refresh_token(),
                "{self.name} token refresh"
            )

    async def _async_try_refresh_token(self) -> None:
        """Try to refresh the token."""
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return
        _LOGGER.debug("%s: Trying to refresh token", self.name)
        try:
            await self.gateway_reader.auth.refresh_token()
        except:  # EnvoyError as err: # TODO: Error handling
            _LOGGER.debug(f"{self.name}: Error refreshing token")
            return
        else:
            self._async_update_cached_token()

    @callback
    def _async_mark_setup_complete(self) -> None:
        """Mark setup as complete and setup token refresh if needed."""
        self._setup_complete = True
        if self._cancel_token_refresh:
            self._cancel_token_refresh()
            self._cancel_token_refresh = None
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return
        self._cancel_token_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_token_if_needed,
            TOKEN_REFRESH_CHECK_INTERVAL,
            cancel_on_shutdown=True,
        )

    async def _async_load_cached_token(self) -> str:
        await self._async_sync_store(load=True)
        return self._store_data.get("token")

    async def _async_update_cached_token(self) -> None:
        """Update saved token in config entry."""
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return
        _LOGGER.debug(f"{self.name}: Updating token in config entry from auth")
        if token := self.gateway_reader.auth.token:
            self._store_data["token"] = token
            self._store_update_pending = True
            await self._async_sync_store()

    async def _async_sync_store(self, load: bool = False) -> None:
        """Sync store."""
        if (self._store and not self._store_data) or load:
            self._store_data = await self._store.async_load() or {}

        if self._store and self._store_update_pending:
            await self._store.async_save(self._store_data)
            self._store_update_pending = False

    def _async_update_saved_token(self) -> None:
        """Update saved token in config entry."""
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return
        # update token in config entry so we can
        # startup without hitting the Cloud API
        # as long as the token is valid
        _LOGGER.debug(f"{self.name}: Updating token in config entry from auth")
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                CONF_TOKEN: self.gateway_reader.auth.token,
            },
        )

    async def _async_update_data(self) -> dict[str, Any]:

        gateway_reader = self.gateway_reader

        for _try in range(2):
            try:
                if not self._setup_complete:
                    await self._async_setup_and_authenticate()
                    self._async_mark_setup_complete()
                await gateway_reader.update(limit_endpoints=ALLOWED_ENDPOINTS)
                return gateway_reader.gateway

            except GatewayAuthenticationError as err:  # TODO: improve
                # try to refresh cookies or get a new token
                # can also be done in the get method
                raise UpdateFailed(
                    f"Gateway authentication error: {err}"
                ) from err
                # continue

            except (EnlightenAuthenticationError, GatewayAuthenticationRequired) as err:
                # token likely expired or firmware changed - re-authenticate
                # Enlighten credentials are likely to be invalid
                if self._setup_complete and _try == 0:
                    self._setup_complete = False
                    continue
                raise ConfigEntryAuthFailed from err

            except httpx.HTTPError as err:
                raise UpdateFailed(
                    f"Error communicating with API: {err}"
                ) from err

        raise RuntimeError("Unreachable code in _async_update_data")


class GatewayCoordinator(GatewayReaderUpdateCoordinator):
    """Copy of GatewayReaderUpdateCoordinator."""

    pass
