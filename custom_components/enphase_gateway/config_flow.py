"""Config flow for Enphase Envoy integration."""

from __future__ import annotations

import logging
import contextlib
from typing import Any

import httpx
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .gateway_reader import GatewayReader
from .const import (
    DOMAIN, CONF_SERIAL_NUM, CONF_USE_TOKEN_AUTH, CONF_TOKEN_CACHE_FILEPATH,
    CONF_TOKEN_RAW, CONF_USE_TOKEN_CACHE, CONF_SINGLE_INVERTER_ENTITIES
)


_LOGGER = logging.getLogger(__name__)

TITLE = "Enphase Gateway"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> GatewayReader:
    """Validate the user input allows us to connect."""
    gateway_reader = GatewayReader(
        data[CONF_HOST],
        username=data.get(CONF_USERNAME, "envoy"),
        password=data.get(CONF_PASSWORD, ""),
        gateway_serial_num=data.get(CONF_SERIAL_NUM, ""),
        use_token_auth=data.get(CONF_USE_TOKEN_AUTH, False),
        # async_client=get_async_client(hass),
        inverters=False,
        
        # preperations for upcoming features
        # token_raw=data.get(CONF_TOKEN_RAW, ""),
        # use_token_cache=data.get(CONF_USE_TOKEN_CACHE, False),
        # token_cache_filepath=data.get(CONF_TOKEN_CACHE_FILEPATH, ""),
        # single_inverter_entities=data.get(CONF_SINGLE_INVERTER_ENTITIES, False),
    )
    
    try:
        await gateway_reader.getData()
    except httpx.HTTPStatusError as err:
        raise InvalidAuth from err
    except (RuntimeError, httpx.HTTPError) as err:
        raise CannotConnect from err

    return gateway_reader


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Gateway."""

    VERSION = 1

    def __init__(self):
        """Initialize an gateway flow."""
        self.ip_address = None
        self.username = None
        self.gateway_type = None
        self._reauth_entry = None
    
    async def async_step_zeroconf(
            self, 
            discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """Handle a config flow initialized by zeroconf discovery.

        Parameters
        ----------
        discovery_info : zeroconf.ZeroconfServiceInfo
            Home Assistant zeroconf discovery information.

        Returns
        -------
        FlowResult
            Config flow result.

        """
        serial_num = discovery_info.properties["serialnum"]
        await self.async_set_unique_id(serial_num)

        # 75 If system option to enable newly discoverd entries is off (by user)
        # and unique_id is this serial_num then skip updating ip
        for entry in self._async_current_entries(include_ignore=False):
            if entry.pref_disable_new_entities and entry.unique_id is not None:
                if entry.unique_id == serial_num:
                    _LOGGER.debug(
                        f"""Gateway autodiscovery/ip update disabled 
                        for: {serial_num}, IP detected: {discovery_info.host} 
                        {entry.unique_id}"""
                    )
                    return self.async_abort(reason="pref_disable_new_entities")

        # autodiscovery is updating the ip address of an existing gateway with 
        # matching serial_num to new detected ip adress
        self.ip_address = discovery_info.host
        self._abort_if_unique_id_configured({CONF_HOST: self.ip_address})
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.unique_id is None
                and CONF_HOST in entry.data
                and entry.data[CONF_HOST] == self.ip_address
            ):  
                if entry.title == TITLE:
                    title = f"{TITLE} {serial_num}"
                else:
                    title = TITLE    
                self.hass.config_entries.async_update_entry(
                    entry, title=title, unique_id=serial_num
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
                return self.async_abort(reason="already_configured")

        return await self.async_step_user()
    
    async def async_step_user(
            self, 
            user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the user step.
        
        Parameters
        ----------
        user_input : dict[str, Any] | None, optional
            Form user input. The default is None.

        Returns
        -------
        FlowResult
            Config flow result.

        """
        errors = {}

        if user_input is not None:
            if (
                not self._reauth_entry
                and user_input[CONF_HOST] in self._get_current_hosts()
            ):
                return self.async_abort(reason="already_configured")
            try:
                gateway_reader = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = user_input.copy() | self._get_placeholders()
                data[CONF_NAME] = self._get_gateway_name(gateway_reader)

                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=data,
                    )
                    return self.async_abort(reason="reauth_successful")

                if (not self.unique_id and 
                    await self._async_set_unique_id_from_gateway(gateway_reader)
                ):
                    data[CONF_NAME] = self._get_gateway_name(gateway_reader)

                if self.unique_id:
                    self._abort_if_unique_id_configured(
                        {CONF_HOST: data[CONF_HOST]}
                    )

                return self.async_create_entry(title=data[CONF_NAME], data=data)

        if self.unique_id:
            self.context["title_placeholders"] = {
                CONF_SERIAL_NUM: self.unique_id,
                CONF_HOST: self.ip_address,
            }
        return self.async_show_form(
            step_id="user",
            data_schema=self._generate_data_shema(),
            errors=errors,
        )

    async def async_step_reauth(
            self, 
            user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reauth.
        
        Parameters
        ----------
        user_input : dict[str, Any] | None, optional
            Form user input. The default is None.

        Returns
        -------
        FlowResult
            Config flow result.

        """
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()
    
    @callback
    def _generate_data_shema(self):
        """Generate schema."""
        schema = {}
        
        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        else:
            schema[vol.Required(CONF_HOST)] = str

        schema[vol.Optional(CONF_USERNAME, default=self.username or "envoy")] = str
        schema[vol.Optional(CONF_PASSWORD, default="")] = str
        schema[vol.Optional(CONF_SERIAL_NUM, default=self.unique_id or "")] = str
        schema[vol.Optional(CONF_USE_TOKEN_AUTH, default=False)] = bool
        return vol.Schema(schema)

    @callback
    def _get_current_hosts(self):
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    def _get_gateway_name(self, gateway_reader: GatewayReader) -> str:
        """Return the name of the gateway."""
        if gateway_type := gateway_reader.gateway_type:
            _name = " ".join(gateway_type.split("_")) # feature for future
            _name = TITLE
        else:
            _name = TITLE
        
        if self.unique_id:
            return f"{_name} {self.unique_id}"
        else:
            return f"{_name}"
    
    async def _async_set_unique_id_from_gateway(
            self, 
            gateway_reader: GatewayReader) -> bool:
        """Set the unique id by fetching it from the gateway."""
        serial_num = None
        with contextlib.suppress(httpx.HTTPError):
            serial_num = await gateway_reader.get_serial_number()
        if serial_num:
            await self.async_set_unique_id(serial_num)
            return True
        return False
    
    def _get_placeholders(self):
        """Return placeholders for config_entry"""
        placeholders = {
            CONF_TOKEN_RAW: "",
            CONF_USE_TOKEN_CACHE: False,
            CONF_TOKEN_CACHE_FILEPATH: "",
            CONF_SINGLE_INVERTER_ENTITIES: True,
        }
        return placeholders
        

    
class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
