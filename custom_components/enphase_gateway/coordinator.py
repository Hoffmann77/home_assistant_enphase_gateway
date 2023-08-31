
from __future__ import annotations

import contextlib
import datetime
from datetime import timedelta
import logging
from typing import Any
import httpx



from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_TOKEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

from .gateway_reader.auth import EnphaseTokenAuth
from .gateway_reader.exceptions import INVALID_AUTH_ERRORS
#from .const import CONF_STORAGE_ENTITIES, SENSORS, ENCHARGE_SENSORS

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
        self._store = Store(hass, STORAGE_VERSION, ".".join([STORAGE_KEY, entry.entry_id]))
        self._store_data = None
        self._store_update_pending = False
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data[CONF_NAME],
            update_interval=SCAN_INTERVAL,
            #always_update=False, # TODO: Added in ha 2023.9
        )
    
    async def _async_setup_and_authenticate(self) -> None:
        """Set up the gateway reader and authenticate."""
        
        gateway_reader = self.gateway_reader
        await gateway_reader.setup()
        if not gateway_reader.serial_number:
            return # TODO add logic
        
        if token := await self._async_load_cached_token():
            await gateway_reader.authenticate(
                username=self.username,
                password=self.password,
                token=token,
                cache_token=False,
                auto_renewal=False,
            )
            self._async_refresh_token_if_needed(dt_util.utcnow())# TODO check method if applicable
            return
        
        await self.gateway_reader.authenticate(
            username=self.username, 
            password=self.password
        )
        
        await self._async_update_cached_token()
          
    @callback
    def _async_refresh_token_if_needed(self, now: datetime.datetime) -> None:
        """Proactively refresh token if its stale in case cloud services goes down."""
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return
        if self.gateway_reader.auth.is_expired:
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
            await self.gateway_reader.auth.refresh()
        except:# EnvoyError as err:
            _LOGGER.debug("%s: Error refreshing token", self.name)
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
        _LOGGER.debug("%s: Updating token in config entry from auth", self.name)
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
        _LOGGER.debug("%s: Updating token in config entry from auth", self.name)
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                CONF_TOKEN: self.gateway_reader.auth.token,
            },
        )    
       
    async def _async_update_data(self) -> dict[str, Any]:
        
        gateway_reader = self.gateway_reader
        
        for tries in range(2):
            try:
                if not self._setup_complete:
                    await self._async_setup_and_authenticate()
                    self._async_mark_setup_complete()
                await gateway_reader.update()
                return gateway_reader.gateway
            except INVALID_AUTH_ERRORS as err:
                if self._setup_complete and tries == 0:
                    # token likely expired or firmware changed, try to re-authenticate
                    self._setup_complete = False
                    continue
                raise ConfigEntryAuthFailed from err
            except httpx.HTTPError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err
                
            # except EnvoyError as err:
            #     raise UpdateFailed(f"Error communicating with API: {err}") from err
                
            # except httpx.HTTPStatusError as err: # TODO implement exceptions
            #     raise ConfigEntryAuthFailed from err
            # except httpx.HTTPError as err:
            #     raise UpdateFailed(f"Error communicating with API: {err}") from err
                
                
        #raise RuntimeError("Unreachable code in _async_update_data")  # pragma: no cover
        
        # data = {}
            
        # for description in SENSORS:
            
        #     # Inverters production data
        #     if description.key == "inverters":
        #         _prod = await gateway_reader.get("inverters_production")
        #         if _prod:
        #             data["inverters_production"] = _prod
                    
        #     # Battery storage data
        #     elif description.key == "batteries":
        #         storages = await gateway_reader.get("battery_storage")
        #         if not isinstance(storages, dict) and len(storages) == 0:
        #             continue
        #         data[description.key] = storages
        #         for uid in storages.keys():
        #             if uid.startswith("encharge"):
        #                 power = await gateway_reader.get("ensemble_power")
        #                 if power:
        #                     data["ensemble_power"] = power
                    
        #     # Total battery storage data
        #     elif description.key in {
        #             "current_battery_capacity",
        #             "total_battery_percentage"
        #     }:
        #         if not data.get("ensemble_secctrl"):
        #             _secctrl = await gateway_reader.get("ensemble_secctrl")
        #             if _secctrl:
        #                 data["ensemble_secctrl"] = _secctrl  
        #         else:
        #             continue
            
        #     elif description.key in {"total_battery_power",}:
        #         continue
            
            
        #     # All other sensor data
        #     else:
        #         _data = await gateway_reader.get(description.key)
        #         if _data and not isinstance(_data, str):
        #                 data[description.key] = _data
                
        # # Encharge battery storage data
        # if ENCHARGE_SENSORS and self.entry.options.get(CONF_STORAGE_ENTITIES, True):
        #     storages = await gateway_reader.get("battery_storage")
        #     ensemble_power = await gateway_reader.get("ensemble_power")
        #     if isinstance(storages, dict) and len(storages) > 0:
        #         _storages = {}
        #         for uid, storage in storages.items():
        #             if uid.startswith("encharge"):
        #                 if ensemble_power:
        #                     serial_num = storage["serial_num"]
        #                     _storages[serial_num] = storage
        #                     _power = {item["serial_num"]: item for item in ensemble_power}
                            
                            
        #                     if power := _power.get(serial_num):
        #                         _storages[serial_num].update(power)
                        
        #         data["encharge"] = _storages
                
        #         # for key in storages.keys():
        #         #     if ensemble_power:
        #         #         if power := ensemble_power.get(key):
        #         #             storages[key].update(power)
                 
        #         # data["encharge"] = storages

        # #data["grid_status"] = gateway_reader.grid_status#()
        # #data["gateway_info"] = gateway_reader.gateway_info#()

        # _LOGGER.debug("Retrieved data from API: %s", data)

        # return data
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    