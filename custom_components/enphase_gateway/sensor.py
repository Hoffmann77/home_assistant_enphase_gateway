"""Home assistant sensors for the Enphase gateway integration."""

from __future__ import annotations

import logging

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
    SensorEntity,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)

from .const import DOMAIN, CONF_INVERTERS, CONF_ENCHARGE_ENTITIES
from .entity import GatewayCoordinatorEntity
from .coordinator import GatewayCoordinator
from .gateway_reader.gateway import BaseGateway
from .gateway_reader.models import (
    EnsemblePower,
    EnsembleInventory,
    ACBatteryStorage,
)


_LOGGER = logging.getLogger(__name__)


def check(val):
    """Check if a value is None."""
    if val is not None:
        return True

    return False


@dataclass(frozen=True, kw_only=True)
class GatewaySensorEntityDescription(SensorEntityDescription):
    """Provide a description of an inverter sensor."""

    value_fn: Callable[[BaseGateway], float | None]
    exists_fn: Callable[[BaseGateway], bool] = lambda _: True


PRODUCTION_SENSORS = (
    GatewaySensorEntityDescription(
        key="production",
        name="Current Power Production",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.production,
        exists_fn=lambda gateway: check(gateway.production),
    ),
    GatewaySensorEntityDescription(
        key="daily_production",
        name="Today's Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.daily_production,
        exists_fn=lambda gateway: check(gateway.daily_production),
    ),
    GatewaySensorEntityDescription(
        key="seven_days_production",
        name="Last Seven Days Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.seven_days_production,
        exists_fn=lambda gateway: check(gateway.seven_days_production),
    ),
    GatewaySensorEntityDescription(
        key="lifetime_production",
        name="Lifetime Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.lifetime_production,
        exists_fn=lambda gateway: check(gateway.lifetime_production),
    ),
)


CONSUMPTION_SENSORS = (
    GatewaySensorEntityDescription(
        key="consumption",
        name="Current Power Consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.consumption,
        exists_fn=lambda gateway: check(gateway.consumption),
    ),
    GatewaySensorEntityDescription(
        key="daily_consumption",
        name="Today's Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.daily_consumption,
        exists_fn=lambda gateway: check(gateway.daily_consumption),
    ),
    GatewaySensorEntityDescription(
        key="seven_days_consumption",
        name="Last Seven Days Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.seven_days_consumption,
        exists_fn=lambda gateway: check(gateway.seven_days_consumption),
    ),
    GatewaySensorEntityDescription(
        key="lifetime_consumption",
        name="Lifetime Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.lifetime_consumption,
        exists_fn=lambda gateway: check(gateway.lifetime_consumption),
    ),
)


GRID_SENSORS = (
    GatewaySensorEntityDescription(
        key="grid_power",
        name="Grid power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.grid_power,
        exists_fn=lambda gateway: check(gateway.grid_power),
    ),
    GatewaySensorEntityDescription(
        key="grid_import",
        name="Grid import power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.grid_import,
        exists_fn=lambda gateway: check(gateway.grid_import),
    ),
    GatewaySensorEntityDescription(
        key="grid_export",
        name="Grid export power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.grid_export,
        exists_fn=lambda gateway: check(gateway.grid_export),
    ),
    GatewaySensorEntityDescription(
        key="lifetime_grid_net_import",
        name="Lifetime net grid import",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.lifetime_grid_net_import,
        exists_fn=lambda gateway: check(gateway.lifetime_grid_net_import),
    ),
    GatewaySensorEntityDescription(
        key="lifetime_grid_net_export",
        name="Lifetime net grid export",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.lifetime_grid_net_export,
        exists_fn=lambda gateway: check(gateway.lifetime_grid_net_export),
    ),
)


@dataclass(frozen=True, kw_only=True)
class InverterSensorEntityDescription(SensorEntityDescription):
    """Provide a description of an inverter sensor."""

    value_fn: Callable[[dict], float | datetime | None]
    exists_fn: Callable[[dict], bool] = lambda _: True


INVERTER_SENSORS = (
    InverterSensorEntityDescription(
        key="lastReportWatts",
        # name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda inverter: inverter.get("lastReportWatts"),
        # exists_fn=lambda entry: bool(entry.options.get("pv_signal")),
    ),
    InverterSensorEntityDescription(
        key="lastReportDate",
        name="Last reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        # value_fn=lambda inverter: inverter.get("lastReportDate"),
        value_fn=lambda inverter: dt_util.utc_from_timestamp(
            inverter["lastReportDate"]
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class ACBatterySensorEntityDescription(SensorEntityDescription):
    """Provide a description for the AC-Battery sensors."""

    value_fn: Callable[[ACBatteryStorage], int | float]
    exists_fn: Callable[[ACBatteryStorage], bool] = lambda _: True


AC_BATTERY_SENSORS = (
    ACBatterySensorEntityDescription(
        key="acb_whNow",
        name="AC-Battery Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        value_fn=attrgetter("whNow"),
        exists_fn=lambda model: model.check("whNow"),
    ),
    ACBatterySensorEntityDescription(
        key="acb_percentFull",
        name="AC-Battery Soc",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=attrgetter("percentFull"),
        exists_fn=lambda model: model.check("percentFull"),
    ),
    ACBatterySensorEntityDescription(
        key="acb_wNow",
        name="AC-Battery power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=attrgetter("wNow"),
        exists_fn=lambda model: model.check("wNow"),
    ),
    ACBatterySensorEntityDescription(
        key="acb_charging_power",
        name="AC-Battery charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=attrgetter("charging_power"),
        exists_fn=lambda model: model.check("charging_power"),
    ),
    ACBatterySensorEntityDescription(
        key="acb_discharging_power",
        name="AC-Battery discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=attrgetter("discharging_power"),
        exists_fn=lambda model: model.check("discharging_power"),
    ),
)


@dataclass(frozen=True, kw_only=True)
class EnsembleSecctrlEntityDescription(SensorEntityDescription):
    """Provide a description of an ensemble power sensor."""

    value_fn: Callable[[dict], int | float | None]
    exists_fn: Callable[[dict], bool] = lambda _: True


ENSEMBLE_SECCTRL_SENSORS = (
    EnsembleSecctrlEntityDescription(
        key="Enc_max_available_capacity",
        name="Encharge capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        value_fn=lambda data: data.get("Enc_max_available_capacity"),
        exists_fn=lambda data: check(data.get("Enc_max_available_capacity")),
    ),
    EnsembleSecctrlEntityDescription(
        key="ENC_agg_avail_energy",
        name="Encharge energy availiable",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        value_fn=lambda data: data.get("ENC_agg_avail_energy"),
        exists_fn=lambda data: check(data.get("ENC_agg_avail_energy")),
    ),
    EnsembleSecctrlEntityDescription(
        key="ENC_agg_backup_energy",
        name="Encharge backup capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        value_fn=lambda data: data.get("ENC_agg_backup_energy"),
        exists_fn=lambda data: check(data.get("ENC_agg_backup_energy")),
    ),
    EnsembleSecctrlEntityDescription(
        key="ENC_agg_soc",
        name="Encharge SoC",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda data: data.get("ENC_agg_soc"),
        exists_fn=lambda data: check(data.get("ENC_agg_soc")),
    ),
    EnsembleSecctrlEntityDescription(
        key="ENC_agg_soh",
        name="Encharge SoH",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("ENC_agg_soh"),
        exists_fn=lambda data: check(data.get("ENC_agg_soh")),
    ),
)


@dataclass(frozen=True, kw_only=True)
class EnsembleInventorySensorEntityDescription(SensorEntityDescription):
    """Provide a description of an ensemble power sensor."""

    value_fn: Callable[[EnsembleInventory], int | float]
    exists_fn: Callable[[EnsembleInventory], bool] = lambda _: True


ENSEMBLE_INVENTORY_SENSORS = (
    EnsembleInventorySensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda model: model.temperature,
        exists_fn=lambda model: model.check("temperature"),
    ),
    EnsembleInventorySensorEntityDescription(
        key="encharge_capacity",
        name="Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda model: model.encharge_capacity,
        exists_fn=lambda model: model.check("encharge_capacity"),
    ),
    EnsembleInventorySensorEntityDescription(
        key="calculated_capacity",
        name="Calculated energy availiable",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda model: model.calculated_capacity,
        exists_fn=lambda model: model.check("calculated_capacity"),
    )
)


@dataclass(frozen=True, kw_only=True)
class EnsemblePowerSensorEntityDescription(SensorEntityDescription):
    """Provide a description for an ensemble power sensor."""

    value_fn: Callable[[EnsemblePower], int | float]
    exists_fn: Callable[[EnsemblePower], bool] = lambda _: True


ENSEMBLE_POWER_SENSORS = (
    EnsemblePowerSensorEntityDescription(
        key="soc",
        name="SoC",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda model: model.soc,
        exists_fn=lambda model: model.check("soc"),
    ),
    EnsemblePowerSensorEntityDescription(
        key="apparent_power_mva",
        name="Apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        value_fn=lambda model: model.apparent_power_mva * 0.001,
        exists_fn=lambda model: model.check("apparent_power_mva"),
    ),
    EnsemblePowerSensorEntityDescription(
        key="real_power_mw",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda model: model.real_power_mw * 0.001,
        exists_fn=lambda model: model.check("real_power_mw"),
    ),
    EnsemblePowerSensorEntityDescription(
        key="charging_power_mw",
        name="Charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda model: model.charging_power_mw * 0.001,
        exists_fn=lambda model: model.check("charging_power_mw"),
    ),
    EnsemblePowerSensorEntityDescription(
        key="discharging_power_mw",
        name="Discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda model: model.discharging_power_mw * 0.001,
        exists_fn=lambda model: model.check("discharging_power_mw"),
    ),
)


ENSEMBLE_AGG_POWER_SENSORS = (
    EnsemblePowerSensorEntityDescription(
        key="apparent_power_mva_agg",
        name="Encharge apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        value_fn=lambda model: model.apparent_power_mva_agg * 0.001,
        exists_fn=lambda model: model.check("apparent_power_mva_agg"),
    ),
    EnsemblePowerSensorEntityDescription(
        key="real_power_mw_agg",
        name="Encharge power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda model: model.real_power_mw_agg * 0.001,
        exists_fn=lambda model: model.check("real_power_mw_agg"),
    ),
    EnsemblePowerSensorEntityDescription(
        key="charging_power_mw_agg",
        name="Encharge charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda model: model.charging_power_mw_agg * 0.001,
        exists_fn=lambda model: model.check("charging_power_mw_agg"),
    ),
    EnsemblePowerSensorEntityDescription(
        key="discharging_power_mw_agg",
        name="Encharge discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda model: model.discharging_power_mw_agg * 0.001,
        exists_fn=lambda model: model.check("discharging_power_mw_agg"),
    ),
)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up envoy sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    options = config_entry.options
    conf_inverters = options.get(CONF_INVERTERS, False)
    conf_encharge_entity = options.get(CONF_ENCHARGE_ENTITIES, False)

    GATEWAY_SENSORS = PRODUCTION_SENSORS + CONSUMPTION_SENSORS + GRID_SENSORS

    # Add the base gateway sensors
    entities: list[Entity] = [
        GatewaySensorEntity(coordinator, description)
        for description in GATEWAY_SENSORS
        if description.exists_fn(coordinator.data)
    ]

    # Add the inverters
    if (data := coordinator.data.inverters) and conf_inverters:
        if conf_inverters == "gateway_sensor":
            entities.extend(
                InverterEntity(coordinator, description, inverter, False)
                for description in INVERTER_SENSORS[:1]
                for inverter in data
            )
        if conf_inverters == "device":
            entities.extend(
                InverterEntity(coordinator, description, inverter, True)
                for description in INVERTER_SENSORS
                for inverter in data
            )

    # Add the AC-Battery sensors
    if data := coordinator.data.ac_battery:
        entities.extend(
            ACBatteryEntity(coordinator, description)
            for description in AC_BATTERY_SENSORS
            if description.exists_fn(data)
        )

    # Add the ensemble secctrl sensors
    if data := coordinator.data.ensemble_secctrl:
        entities.extend(
            EnsembleSecctrlEntity(coordinator, description)
            for description in ENSEMBLE_SECCTRL_SENSORS
            if description.exists_fn(data)
        )

    # Add the ensemble aggregated power sensors
    if data := coordinator.data.ensemble_power:
        entities.extend(
            EnsembleAggregatedPowerEntity(coordinator, description)
            for description in ENSEMBLE_AGG_POWER_SENSORS
            if description.exists_fn(data)
        )

    # Enphase storage sensors --------------------------------------------->

    # Add the ensemble power sensors
    if (data := coordinator.data.ensemble_power) and conf_encharge_entity:
        entities.extend(
            EnsemblePowerEntity(coordinator, description, serial_num)
            for description in ENSEMBLE_POWER_SENSORS
            for serial_num in data.devices.keys()
            if description.exists_fn(data[serial_num])
        )

    # Add the ensemble inventory sensors
    if (data := coordinator.data.ensemble_inventory) and conf_encharge_entity:
        entities.extend(
            EnsembleInventoryEntity(coordinator, description, serial_num)
            for description in ENSEMBLE_INVENTORY_SENSORS
            for serial_num in data
            if description.exists_fn(data[serial_num])
        )

    _LOGGER.debug(f"Adding the following entities: {entities}")

    async_add_entities(entities)


class GatewaySensorEntity(GatewayCoordinatorEntity, SensorEntity):
    """Implementation of the Gateway entity."""

    def __init__(
        self,
        coordinator: GatewayCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{self.gateway_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.gateway_serial_num))},
            manufacturer="Enphase",
            model=self.coordinator.gateway_reader.name,
            name=self.coordinator.name,
            sw_version=str(self.coordinator.gateway_reader.firmware_version),
            serial_number=self.gateway_serial_num,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        assert self.data is not None
        return self.entity_description.value_fn(self.data)


class InverterEntity(GatewaySensorEntity):
    """Implementation of the Inverter entity."""

    entity_description: InverterSensorEntityDescription

    def __init__(
            self,
            coordinator,
            description,
            serial_number: str,
            as_device: bool,
    ) -> None:
        """Initialize Gateway inverter entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        # self._attr_unique_id = f"{serial_number}_{description.key}"
        if as_device:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(self._serial_number))},
                name=f"Inverter {serial_number}",
                manufacturer="Enphase",
                model="Inverter",
                via_device=(DOMAIN, self.gateway_serial_num),
            )

    @property
    def unique_id(self) -> str:
        """Return the entity's unique_id."""
        # TODO: improve unique ids.
        # Originally there was only one inverter sensor, so we don't want to
        # break existing installations by changing the unique_id.
        if self.entity_description.key == "lastReportWatts":
            return self._serial_number
        else:
            return f"{self._serial_number}_{self.entity_description.key}"

    @property
    def name(self):
        """Return the entity name."""
        return f"Inverter {self._serial_number}"
        # return f"{self.entity_description.name} {self._serial_number}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        inverters = self.data.get("inverters")
        assert inverters is not None
        if self._serial_number not in inverters:
            _LOGGER.debug(
                f"Inverter {self._serial_number} not in returned inverters.",
            )
            return None

        inverter = inverters.get(self._serial_number, {})
        assert inverter["lastReportDate"]
        return self.entity_description.value_fn(inverter)


class ACBatteryEntity(GatewaySensorEntity):
    """Implementation of the AC-Battery entity."""

    entity_description: ACBatterySensorEntityDescription

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        ac_battery = self.data.ac_battery
        assert ac_battery is not None
        return self.entity_description.value_fn(ac_battery)


class EnsembleSecctrlEntity(GatewaySensorEntity):
    """Implementation of the Ensemble secctrl entity."""

    entity_description: EnsembleSecctrlEntityDescription

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        ensemble_secctrl = self.data.ensemble_secctrl
        assert ensemble_secctrl is not None
        return self.entity_description.value_fn(ensemble_secctrl)


class EnsembleAggregatedPowerEntity(GatewaySensorEntity):
    """Implementation of the aggregated Ensemble power entity."""

    entity_description: EnsemblePowerSensorEntityDescription

    @property
    def unique_id(self) -> str:
        """Return the entity's unique_id."""
        # uses `encharge` as prefix for legacy support. (05/2024)
        key = f"encharge_{self.entity_description.key}"
        return f"{self.gateway_serial_num}_{key}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        ensemble_power = self.data.ensemble_power
        assert ensemble_power is not None
        return self.entity_description.value_fn(ensemble_power)


class StorageSensorEntity(GatewaySensorEntity):
    """Implementation of the storage entity.

    Add entities as seperate storage device.

    """

    def __init__(
            self,
            coordinator,
            description,
            serial_number: str,
    ) -> None:
        """Initialize Gateway inverter entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._serial_number))},
            name=f"Encharge {self._serial_number}",
            manufacturer="Enphase",
            model="Encharge",
            via_device=(DOMAIN, self.gateway_serial_num)
        )


class EnsembleInventoryEntity(StorageSensorEntity):
    """Implementation of the Ensemble inventory entity."""

    entity_description: EnsembleInventorySensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        ensemble_inventory = self.data.ensemble_inventory
        assert ensemble_inventory is not None
        return self.entity_description.value_fn(
            ensemble_inventory[self._serial_number]
        )


class EnsemblePowerEntity(StorageSensorEntity):
    """Implementation of the Ensemble power entity."""

    entity_description: EnsemblePowerSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        ensemble_power = self.data.ensemble_power
        assert ensemble_power is not None
        return self.entity_description.value_fn(
            ensemble_power[self._serial_number]
        )
