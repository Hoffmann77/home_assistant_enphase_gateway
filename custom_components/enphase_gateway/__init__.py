"""The Enphase Envoy integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .gateway_reader import GatewayReader
from .coordinator import GatewayReaderUpdateCoordinator
from .const import ( 
    DOMAIN, PLATFORMS, CONF_GET_INVERTERS, CONF_CACHE_TOKEN, 
    CONF_STORAGE_ENTITIES,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enphase Gateway from a config entry."""
    
    host = entry.data[CONF_HOST]
    reader = GatewayReader(host, get_async_client(hass, verify_ssl=False))
    coordinator = GatewayReaderUpdateCoordinator(hass, reader, entry)
    
    await coordinator.async_config_entry_first_refresh()
    
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=reader.serial_number
        )
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

    
    # config = entry.data
    # options = entry.options
    # name = config[CONF_NAME]
    # store = Store(hass, STORE_VERSION, ".".join([STORE_KEY, entry.entry_id]))

    # gateway_reader = GatewayReader(
    #     config[CONF_HOST],
    #     username=config[CONF_USERNAME],
    #     password=config[CONF_PASSWORD],
    #     gateway_serial_num=config[CONF_SERIAL_NUM],
    #     use_token_auth=config.get(CONF_USE_TOKEN_AUTH, False),
    #     cache_token=options.get(CONF_CACHE_TOKEN, False),
    #     get_inverters=options.get(CONF_GET_INVERTERS, False),
    #     store=store
    #     # async_client=get_async_client(hass),
    # )
    
    # async def async_update_data():
    #     """Fetch data from API endpoint."""
    #     data = {}
    #     async with async_timeout.timeout(30):
    #         try:
    #             await gateway_reader.getData()
    #         except httpx.HTTPStatusError as err:
    #             raise ConfigEntryAuthFailed from err
    #         except httpx.HTTPError as err:
    #             raise UpdateFailed(f"Error communicating with API: {err}") from err
            
    #         for description in SENSORS:
                
    #             # Inverters production data
    #             if description.key == "inverters":
    #                 _prod = await gateway_reader.get("inverters_production")
    #                 if _prod:
    #                     data["inverters_production"] = _prod
                        
    #             # Battery storage data
    #             elif description.key == "batteries":
    #                 storages = await gateway_reader.get("battery_storage")
    #                 if not isinstance(storages, dict) and len(storages) == 0:
    #                     continue
    #                 data[description.key] = storages
    #                 for uid in storages.keys():
    #                     if uid.startswith("encharge"):
    #                         power = await gateway_reader.get("ensemble_power")
    #                         if power:
    #                             data["ensemble_power"] = power
                        
    #             # Total battery storage data
    #             elif description.key in {
    #                     "current_battery_capacity",
    #                     "total_battery_percentage"
    #             }:
    #                 if not data.get("ensemble_secctrl"):
    #                     _secctrl = await gateway_reader.get("ensemble_secctrl")
    #                     if _secctrl:
    #                         data["ensemble_secctrl"] = _secctrl  
    #                 else:
    #                     continue
                
    #             elif description.key in {"total_battery_power",}:
    #                 continue
                
                
    #             # All other sensor data
    #             else:
    #                 _data = await gateway_reader.get(description.key)
    #                 if _data and not isinstance(_data, str):
    #                         data[description.key] = _data
                    
    #         # Encharge battery storage data
    #         if ENCHARGE_SENSORS and options.get(CONF_STORAGE_ENTITIES, True):
    #             storages = await gateway_reader.get("battery_storage")
    #             ensemble_power = await gateway_reader.get("ensemble_power")
    #             if isinstance(storages, dict) and len(storages) > 0:
    #                 _storages = {}
    #                 for uid, storage in storages.items():
    #                     if uid.startswith("encharge"):
    #                         if ensemble_power:
    #                             serial_num = storage["serial_num"]
    #                             _storages[serial_num] = storage
    #                             _power = {item["serial_num"]: item for item in ensemble_power}
                                
                                
    #                             if power := _power.get(serial_num):
    #                                 _storages[serial_num].update(power)
                            
    #                 data["encharge"] = _storages
                    
    #                 # for key in storages.keys():
    #                 #     if ensemble_power:
    #                 #         if power := ensemble_power.get(key):
    #                 #             storages[key].update(power)
                     
    #                 # data["encharge"] = storages

    #         #data["grid_status"] = gateway_reader.grid_status#()
    #         #data["gateway_info"] = gateway_reader.gateway_info#()

    #         _LOGGER.debug("Retrieved data from API: %s", data)

    #         return data

    # coordinator = DataUpdateCoordinator(
    #     hass,
    #     _LOGGER,
    #     name=f"envoy {name}",
    #     update_method=async_update_data,
    #     update_interval=SCAN_INTERVAL,
    # )

    # try:
    #     await coordinator.async_config_entry_first_refresh()
    # except ConfigEntryAuthFailed:
    #     gateway_reader.get_inverters = False
    #     await coordinator.async_config_entry_first_refresh()

    # if not entry.unique_id:
    #     try:
    #         serial = await gateway_reader.get_serial_number()
    #     except httpx.HTTPError:
    #         pass
    #     else:
    #         hass.config_entries.async_update_entry(entry, unique_id=serial)

    # hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
    #     COORDINATOR: coordinator,
    #     NAME: name,
    # }

    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(f"Migrating from version {config_entry.version}")

    if config_entry.version == 1:

        new = {**config_entry.data}
        
        # Remove unwanted variables
        new.pop("token_raw", None)
        new.pop("use_token_cache", None)
        new.pop("token_cache_filepath", None)
        new.pop("single_inverter_entities", None)
        
        options = {
            CONF_GET_INVERTERS: True,
            CONF_STORAGE_ENTITIES: True,
            CONF_CACHE_TOKEN: True,
        }
        
        config_entry.version = 2
        hass.config_entries.async_update_entry(
            config_entry,
            data=new,
            options=options
        )

    _LOGGER.info("Migration to version {config_entry.version} successful")

    return True

