"""The Enphase Envoy integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import httpx
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

from .gateway_reader import GatewayReader
from .const import (
    COORDINATOR, DOMAIN, NAME, PLATFORMS, SENSORS, CONF_USE_TOKEN_AUTH, 
    CONF_SERIAL_NUM, ENCHARGE_SENSORS, CONF_GET_INVERTERS, CONF_CACHE_TOKEN,
    CONF_STORAGE_ENTITIES,
)


SCAN_INTERVAL = timedelta(seconds=60)
STORE_VERSION = 1
STORE_KEY = "enphase_gateway"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enphase Gateway from a config entry."""
    config = entry.data
    options = entry.options
    name = config[CONF_NAME]
    store = Store(hass, STORE_VERSION, ".".join([STORE_KEY, entry.entry_id]))

    gateway_reader = GatewayReader(
        config[CONF_HOST],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD],
        gateway_serial_num=config[CONF_SERIAL_NUM],
        use_token_auth=config.get(CONF_USE_TOKEN_AUTH, False),
        cache_token=options.get(CONF_CACHE_TOKEN, False),
        get_inverters=options.get(CONF_GET_INVERTERS, False),
        store=store
        # async_client=get_async_client(hass),
    )
    
    async def async_update_data():
        """Fetch data from API endpoint."""
        data = {}
        async with async_timeout.timeout(30):
            try:
                await gateway_reader.getData()
            except httpx.HTTPStatusError as err:
                raise ConfigEntryAuthFailed from err
            except httpx.HTTPError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err
            
            for description in SENSORS:
                if description.key == "inverters":
                    production = await gateway_reader.inverters_production()
                    data["inverters_production"] = production
                
                elif description.key == "batteries":
                    storages = await gateway_reader.battery_storage()
                    if isinstance(storages, dict) and len(storages) > 0:
                        data[description.key] = storages
                
                elif description.key in {
                        "current_battery_capacity",
                        "total_battery_percentage"
                }:
                    continue
                
                else:
                    func = getattr(gateway_reader, description.key)
                    data[description.key] = await func()
            
            if ENCHARGE_SENSORS and options.get(CONF_STORAGE_ENTITIES, True):
                storages = await gateway_reader.battery_storage()
                storages = storages.get("ENCHARGE")
                ensemble_power = await gateway_reader.ensemble_power()
                if isinstance(storages, dict) and len(storages) > 0:
                    for key in storages.keys():
                        if ensemble_power:
                            if power := ensemble_power.get(key):
                                storages[key].update(power)
                     
                    data["encharge"] = storages

            data["grid_status"] = await gateway_reader.grid_status()
            data["gateway_info"] = await gateway_reader.gateway_info()

            _LOGGER.debug("Retrieved data from API: %s", data)

            return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"envoy {name}",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        gateway_reader.get_inverters = False
        await coordinator.async_config_entry_first_refresh()

    if not entry.unique_id:
        try:
            serial = await gateway_reader.get_serial_number()
        except httpx.HTTPError:
            pass
        else:
            hass.config_entries.async_update_entry(entry, unique_id=serial)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        NAME: name,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


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

