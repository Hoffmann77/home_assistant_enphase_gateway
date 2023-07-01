"""The Enphase Envoy integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import httpx
import async_timeout
from numpy import isin
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COORDINATOR, DOMAIN, NAME, PLATFORMS, SENSORS, CONF_USE_ENLIGHTEN, CONF_SERIAL
from .gateway_reader import GatewayReader


SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enphase Gateway from a config entry."""
    config = entry.data
    name = config[CONF_NAME]

    gateway_reader = GatewayReader(
        config[CONF_HOST],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD],
        gateway_serial_num=config[CONF_SERIAL],
        use_token_auth=config.get(CONF_USE_ENLIGHTEN, False),
        # async_client=get_async_client(hass),
        inverters=True,
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
                    data[
                        "inverters_production"
                    ] = await gateway_reader.inverters_production()

                elif description.key == "batteries":
                    battery_data = await gateway_reader.battery_storage()
                    if isinstance(battery_data, list) and len(battery_data) > 0:
                        battery_dict = {}
                        for item in battery_data:
                            battery_dict[item["serial_num"]] = item

                        data[description.key] = battery_dict

                elif (description.key not in ["current_battery_capacity", "total_battery_percentage"]):
                    data[description.key] = await getattr(
                        gateway_reader, description.key
                    )()

            data["grid_status"] = await gateway_reader.grid_status()

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
            serial = await gateway_reader.get_full_serial_number()
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
