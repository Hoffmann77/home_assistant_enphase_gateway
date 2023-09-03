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

