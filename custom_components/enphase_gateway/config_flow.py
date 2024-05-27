"""Config flow for Enphase gateway integration."""

from __future__ import annotations

import re
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import selector
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from .gateway_reader import GatewayReader
from .exceptions import CannotConnect
from .const import (
    DOMAIN, CONF_SERIAL_NUM, CONF_CACHE_TOKEN, CONF_USE_LEGACY_NAME,
    CONF_ENCHARGE_ENTITIES, CONFIG_FLOW_USER_ERROR, CONF_INVERTERS,
    ALLOWED_ENDPOINTS, CONF_DATA_UPDATE_INTERVAL
)


_LOGGER = logging.getLogger(__name__)

DEFAULT_TITLE = "Enphase Gateway"
LEGACY_TITLE = "Envoy"


async def validate_input(
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
) -> GatewayReader:
    """Validate that the user input allows us to connect."""
    gateway_reader = GatewayReader(
        host,
        get_async_client(hass, verify_ssl=False)
    )
    await gateway_reader.prepare()
    await gateway_reader.authenticate(username=username, password=password)
    await gateway_reader.update(limit_endpoints=ALLOWED_ENDPOINTS)
    return gateway_reader


class GatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Gateway."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self):
        """Initialize an gateway flow."""
        self.ip_address = None
        self.username = None
        self._reauth_entry = None
        self._discovery_info = None
        self._gateway_reader = None
        self._step_data = {}

    async def async_step_zeroconf(
            self,
            discovery_info: zeroconf.ZeroconfServiceInfo,
    ) -> FlowResult:
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
                #  update title with serial_num if title was not changed
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
            user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
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
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if self._reauth_entry:
            host = self._reauth_entry.data[CONF_HOST]
        else:
            host = (user_input or {}).get(CONF_HOST) or self.ip_address or ""

        if user_input is not None:
            use_legacy_name = user_input.pop(CONF_USE_LEGACY_NAME, False)

            if not self._reauth_entry and host in self._get_current_hosts():
                return self.async_abort(reason="already_configured")

            try:
                gateway_reader = await validate_input(
                    self.hass,
                    host,
                    username=user_input.get(CONF_USERNAME),
                    password=user_input.get(CONF_PASSWORD),
                )
            except CONFIG_FLOW_USER_ERROR as err:
                r = re.split('(?<=.)(?=[A-Z])', err.__class__.__name__)
                errors["base"] = "_".join(r).lower()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._gateway_reader = gateway_reader
                name = self._generate_name(use_legacy_name)

                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=self._reauth_entry.data | user_input,
                    )
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(
                            self._reauth_entry.entry_id
                        )
                    )
                    return self.async_abort(reason="reauth_successful")

                if not self.unique_id:
                    await self.async_set_unique_id(
                        gateway_reader.serial_number
                    )
                    name = self._generate_name(use_legacy_name)
                    #  data[CONF_NAME] = self._generate_name(use_legacy_name)

                else:
                    self._abort_if_unique_id_configured()

                _data = {CONF_HOST: host, CONF_NAME: name} | user_input
                self._step_data["user"] = _data
                return await self.async_step_config()

        if self.unique_id:
            self.context["title_placeholders"] = {
                CONF_SERIAL_NUM: self.unique_id,
                CONF_HOST: self.ip_address,
            }

        return self.async_show_form(
            step_id="user",
            data_schema=self._generate_shema_user_step(),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_config(
            self,
            user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
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
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        step_data = self._step_data["user"]

        if user_input is not None:
            return self.async_create_entry(
                title=step_data[CONF_NAME],
                data=step_data,
                options=user_input,
            )

        description_placeholders["gateway_type"] = self._gateway_reader.name

        return self.async_show_form(
            step_id="config",
            data_schema=self._generate_shema_config_step(),
            errors=errors,
            description_placeholders=description_placeholders
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

        if self._reauth_entry is not None:
            if unique_id := self._reauth_entry.unique_id:
                await self.async_set_unique_id(
                    unique_id,
                    raise_on_progress=False
                )

        return await self.async_step_user()

    @callback
    def _generate_shema_user_step(self):
        """Generate schema."""
        if self.ip_address:
            ip_address_val = vol.In([self.ip_address])
        else:
            ip_address_val = str

        schema = {
            vol.Required(CONF_HOST, default=self.ip_address): ip_address_val,
            vol.Optional(CONF_USERNAME, default=self.username or "envoy"): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
            vol.Optional(CONF_USE_LEGACY_NAME, default=False): bool,
        }
        return vol.Schema(schema)

    @callback
    def _generate_shema_config_step(self):
        """Generate schema."""
        schema = {
            vol.Required(CONF_INVERTERS): selector(
                {
                    "select": {
                        "translation_key": CONF_INVERTERS,
                        "mode": "dropdown",
                        "options": ["gateway_sensor", "device", "disabled"],
                    }
                }
            ),
        }

        if self._gateway_reader.gateway.encharge_inventory:
            schema.update(
                {vol.Optional(CONF_ENCHARGE_ENTITIES, default=True): bool}
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

    # async def _async_set_unique_id_from_gateway(
    #         self,
    #         gateway_reader: GatewayReader) -> bool:
    #     """Set the unique id by fetching it from the gateway."""
    #     serial_num = None
    #     with contextlib.suppress(httpx.HTTPError):
    #         serial_num = await gateway_reader.get_serial_number()
    #     if serial_num:
    #         await self.async_set_unique_id(serial_num)
    #         return True
    #     return False

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
        default_inverters = options.get(CONF_INVERTERS, "disabled")
        # default_data_update_interval = options.get(
        #     CONF_DATA_UPDATE_INTERVAL, "moderate"
        # )
        schema = {
            vol.Optional(
                CONF_INVERTERS, default=default_inverters): selector(
                    {
                        "select": {
                            "translation_key": CONF_INVERTERS,
                            "mode": "dropdown",
                            "options": [
                                "gateway_sensor", "device", "disabled"
                            ],
                        }
                    }
            ),
        }
        if CONF_ENCHARGE_ENTITIES in options_keys:
            schema.update({
                vol.Optional(
                    CONF_ENCHARGE_ENTITIES,
                    default=options.get(CONF_ENCHARGE_ENTITIES)
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
