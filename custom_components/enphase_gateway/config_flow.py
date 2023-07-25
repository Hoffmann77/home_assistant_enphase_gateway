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

from .gateway_reader import GatewayReader
from .exceptions import (
    CannotConnect, InvalidAuth, EnlightenInvalidAuth, InvalidToken,
    EnlightenUnauthorized, InvalidEnphaseToken
)
from .const import (
    DOMAIN, CONF_SERIAL_NUM, CONF_USE_TOKEN_AUTH, CONF_TOKEN_RAW,
    CONF_CACHE_TOKEN, CONF_GET_INVERTERS, CONF_USE_LEGACY_NAME,
    CONF_STORAGE_ENTITIES
)


_LOGGER = logging.getLogger(__name__)

DEFAULT_TITLE = "Enphase Gateway"
LEGACY_TITLE = "Envoy"


async def validate_input(
        hass: HomeAssistant,
        data: dict[str, Any]) -> GatewayReader:
    """Validate the user input allows us to connect."""
    gateway_reader = GatewayReader(
        data[CONF_HOST],
        username=data.get(CONF_USERNAME, "envoy"),
        password=data.get(CONF_PASSWORD, ""),
        gateway_serial_num=data.get(CONF_SERIAL_NUM, ""),
        use_token_auth=data.get(CONF_USE_TOKEN_AUTH, False),
        get_inverters=False,
        # async_client=get_async_client(hass),
        
        # preperations for upcoming features
        # token_raw=data.get(CONF_TOKEN_RAW, ""),
    )
    
    try:
        await gateway_reader.getData()
    except InvalidEnphaseToken as err:
        raise InvalidToken from err
    except EnlightenUnauthorized as err:
        raise EnlightenInvalidAuth from err
    except httpx.HTTPStatusError as err:
        raise InvalidAuth from err
    except (RuntimeError, httpx.HTTPError) as err:
        raise CannotConnect from err

    return gateway_reader


class GatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Gateway."""

    VERSION = 2

    def __init__(self):
        """Initialize an gateway flow."""
        self.ip_address = None
        self.username = None
        self._gateway_reader = None
        self._reauth_entry = None
        self._user_step_data = None
        self._discovery_info = None
        
    async def async_step_zeroconf(
            self, 
            discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """Handle a config flow initialized by zeroconf discovery.
        
        Update the IP adress of discovered devices unless the system 
        option to enable newly discoverd entries is off.
        
        Parameters
        ----------
        discovery_info : zeroconf.ZeroconfServiceInfo
            Home Assistant zeroconf discovery information.

        Returns
        -------
        FlowResult
            Config flow result.
            
        """
        _LOGGER.debug(f"""Zeroconf discovery: {discovery_info}""")
        self._discovery_info = discovery_info
        serial_num = discovery_info.properties["serialnum"]
        current_entry = await self.async_set_unique_id(serial_num)
        
        if current_entry and current_entry.pref_disable_new_entities:
            _LOGGER.debug(
                f"""
                Gateway autodiscovery/ip update disabled for: {serial_num},
                IP detected: {discovery_info.host} {current_entry.unique_id}
                """
            )
            return self.async_abort(reason="pref_disable_new_entities")  
        
        self.ip_address = discovery_info.host
        self._abort_if_unique_id_configured({CONF_HOST: self.ip_address})
        
        # set unique_id if not set for an entry with the same IP adress
        for entry in self._async_current_entries(include_ignore=False):
            if not entry.unique_id and entry.data.get(CONF_HOST) == self.ip_adress:
                # update title with serial_num if title was not changed
                if entry.title in {DEFAULT_TITLE, LEGACY_TITLE}:
                    title = f"{entry.title} {serial_num}"
                else:
                    title = entry.title
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
            use_legacy_name = user_input.pop(CONF_USE_LEGACY_NAME, False)
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
            except EnlightenInvalidAuth:
                errors["base"] = "enlighten_invalid_auth"
            except InvalidToken:
                errors["base"] = "invalid_token"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._gateway_reader = gateway_reader
                data = user_input.copy()
                data[CONF_NAME] = self._generate_name(use_legacy_name)
                
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=data,
                    )
                    return self.async_abort(reason="reauth_successful")
                
                if not self.unique_id:
                    if serial_num := await gateway_reader.get_serial_number():
                        await self.async_set_unique_id(serial_num)    
                        data[CONF_NAME] = self._generate_name(use_legacy_name)
                
                self._abort_if_unique_id_configured()
                self._user_step_data = data
                return await self.async_step_config()
                
        if self.unique_id:
            self.context["title_placeholders"] = {
                CONF_SERIAL_NUM: self.unique_id,
                CONF_HOST: self.ip_address,
            }
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_step_user_shema(),
            errors=errors,
        )

    async def async_step_config(
            self, 
            user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the configuration step.
        
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
        user_step_data = self._user_step_data
        if user_input is not None:
            options = user_input.copy()

            return self.async_create_entry(
                title=user_step_data[CONF_NAME], 
                data=user_step_data,
                options=options
            )
        
        gateway_info = await self._gateway_reader.gateway_info()
        placeholders = {
            "gateway_type": gateway_info.get("gateway_type", ""),
        }
        
        return self.async_show_form(
            step_id="config",
            data_schema=self._get_step_config_shema(),
            errors=errors,
            description_placeholders=placeholders
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
    def _get_step_user_shema(self):
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
        schema[vol.Optional(CONF_USE_LEGACY_NAME, default=False)] = bool
        return vol.Schema(schema)
    
    @callback
    def _get_step_config_shema(self):
        """Generate schema."""
        schema = {
            vol.Optional(CONF_GET_INVERTERS, default=True): bool,
        }
        if self._gateway_reader.storages:
            schema.update(
                {vol.Optional(CONF_STORAGE_ENTITIES, default=True): bool}
            )
        if self._gateway_reader.use_token_auth:
            schema.update(
                {vol.Optional(CONF_CACHE_TOKEN, default=True): bool}
            )
        return vol.Schema(schema)

    @callback
    def _get_current_hosts(self):
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }
    
    def _generate_name(self, use_legacy_name=False):
        """Return the name of the entity."""
        name = LEGACY_TITLE if use_legacy_name else DEFAULT_TITLE
        if self.unique_id:
            return f"{name} {self.unique_id}"
        return name
    
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
    
    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: config_entries.ConfigEntry
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return GatewayOptionsFlow(config_entry)
    
    
class GatewayOptionsFlow(config_entries.OptionsFlow):
    """Handle a options flow for Enphase Gateway."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
    
    async def async_step_init(
            self, 
            user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        return self.async_show_form(
            step_id="init",
            data_schema=self._generate_data_shema()
        )

    @callback
    def _generate_data_shema(self):
        """Generate schema."""
        options = self.config_entry.options
        options_keys = options.keys()
        schema = {
            vol.Optional(
                CONF_GET_INVERTERS,
                default=options.get(CONF_GET_INVERTERS, True)
            ): bool,   
        }
        if CONF_STORAGE_ENTITIES in options_keys:
            schema.update({
                vol.Optional(
                    CONF_STORAGE_ENTITIES,
                    default=options.get(CONF_STORAGE_ENTITIES)
                ): bool,
            })
        if CONF_CACHE_TOKEN in options_keys:
            schema.update({
                vol.Optional(
                    CONF_CACHE_TOKEN,
                    default=options.get(CONF_CACHE_TOKEN)
                ): bool,
            })
        return vol.Schema(schema)

