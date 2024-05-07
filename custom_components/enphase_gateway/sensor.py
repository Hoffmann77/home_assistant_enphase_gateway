"""Home assistant sensors for the Enphase gateway integration."""

from __future__ import annotations

import logging

from collections.abc import Callable
from dataclasses import dataclass, replace
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
)

from .const import DOMAIN,  ICON, CONF_INVERTERS, CONF_ENCHARGE_ENTITIES
from .entity import GatewaySensorBaseEntity, GatewayCoordinatorEntity
from .coordinator import GatewayReaderUpdateCoordinator, GatewayCoordinator
from .gateway_reader.models.ensemble import EnchargePower
from .gateway_reader.models.ac_battery import ACBatteryStorage


_LOGGER = logging.getLogger(__name__)


def check(val):
    """Check if a value is None."""
    if val is not None:
        return True

    return False


@dataclass(frozen=True, kw_only=True)
class BaseSensorEntityDescription(SensorEntityDescription):
    """Provide a description of an inverter sensor."""

    value_fn: Callable[[dict], float | None]
    exists_fn: Callable[[dict], bool] = lambda _: True


PRODUCTION_SENSORS = (
    BaseSensorEntityDescription(
        key="production",
        name="Current Power Production",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("production"),
        exists_fn=lambda gateway: check(gateway.production),
    ),
    BaseSensorEntityDescription(
        key="daily_production",
        name="Today's Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("daily_production"),
        exists_fn=lambda gateway: check(gateway.daily_production),
    ),
    BaseSensorEntityDescription(
        key="seven_days_production",
        name="Last Seven Days Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("seven_days_production"),
        exists_fn=lambda gateway: check(gateway.seven_days_production),
    ),
    BaseSensorEntityDescription(
        key="lifetime_production",
        name="Lifetime Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("lifetime_production"),
        exists_fn=lambda gateway: check(gateway.lifetime_production),
    ),
)


CONSUMPTION_SENSORS = (
    BaseSensorEntityDescription(
        key="consumption",
        name="Current Power Consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("consumption"),
        exists_fn=lambda gateway: check(gateway.consumption),
    ),
    BaseSensorEntityDescription(
        key="daily_consumption",
        name="Today's Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("daily_consumption"),
        exists_fn=lambda gateway: check(gateway.daily_consumption),
    ),
    BaseSensorEntityDescription(
        key="seven_days_consumption",
        name="Last Seven Days Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("seven_days_consumption"),
        exists_fn=lambda gateway: check(gateway.seven_days_consumption),
    ),
    BaseSensorEntityDescription(
        key="lifetime_consumption",
        name="Lifetime Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("lifetime_consumption"),
        exists_fn=lambda gateway: check(gateway.lifetime_consumption),
    ),
)


GRID_SENSORS = (
    BaseSensorEntityDescription(
        key="grid_import",
        name="Grid import",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("grid_import"),
        exists_fn=lambda gateway: check(gateway.grid_import),
    ),
    BaseSensorEntityDescription(
        key="grid_export",
        name="Grid export",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("grid_export"),
        exists_fn=lambda gateway: check(gateway.grid_export),
    ),
    BaseSensorEntityDescription(
        key="grid_import_lifetime",
        name="Lifetime grid import",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("grid_import_lifetime"),
        exists_fn=lambda gateway: check(gateway.grid_import_lifetime),
    ),
    BaseSensorEntityDescription(
        key="grid_export_lifetime",
        name="Lifetime grid export",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda gateway: gateway.get("grid_export_lifetime"),
        exists_fn=lambda gateway: check(gateway.grid_export_lifetime),
    ),
)


BASE_SENSORS = PRODUCTION_SENSORS + CONSUMPTION_SENSORS + GRID_SENSORS


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
            inverter["lastReportDate"].last_report_date
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class ACBatterySensorEntityDescription(SensorEntityDescription):
    """Provide a description of an inverter sensor."""

    value_fn: Callable[[ACBatteryStorage], int | float]
    exists_fn: Callable[[dict], bool] = lambda _: True


AC_BATTERY_SENSORS = (
    ACBatterySensorEntityDescription(
        key="whNow",
        name="AC-Battery Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        value_fn=attrgetter("whNow"),
        exists_fn=lambda model: check(model.whNow),
    ),
    ACBatterySensorEntityDescription(
        key="percentFull",
        name="AC-Battery Soc",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=attrgetter("percentFull"),
        exists_fn=lambda model: check(model.percentFull),
    ),
    ACBatterySensorEntityDescription(
        key="wNow",
        name="AC-Battery power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=attrgetter("wNow"),
        exists_fn=lambda model: check(model.wNow),
    ),
    ACBatterySensorEntityDescription(
        key="charging_power",
        name="AC-Battery charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=attrgetter("charging_power"),
        exists_fn=lambda model: check(model.charging_power),
    ),
    ACBatterySensorEntityDescription(
        key="discharging_power",
        name="AC-Battery discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=attrgetter("discharging_power"),
        exists_fn=lambda model: check(model.discharging_power),
    ),
)


ENCHARGE_AGG_SENSORS = (
    SensorEntityDescription(
        key="Enc_max_available_capacity",
        name="ENCHARGE capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
    SensorEntityDescription(
        key="ENC_agg_avail_energy",
        name="ENCHARGE energy availiable",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
    SensorEntityDescription(
        key="ENC_agg_backup_energy",
        name="ENCHARGE backup capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
    SensorEntityDescription(
        key="ENC_agg_soc",
        name="ENCHARGE SoC",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY
    ),
    SensorEntityDescription(
        key="ENC_agg_soh",
        name="ENCHARGE SoH",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


# ENCHARGE_AGG_POWER_SENSORS = (
#     SensorEntityDescription(
#         key="real_power_mw",
#         name="ENCHARGE power",
#         native_unit_of_measurement=UnitOfPower.WATT,
#         state_class=SensorStateClass.MEASUREMENT,
#         device_class=SensorDeviceClass.POWER
#     ),
#     SensorEntityDescription(
#         key="apparent_power_mva",
#         name="ENCHARGE apparent power",
#         native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
#         state_class=SensorStateClass.MEASUREMENT,
#         device_class=SensorDeviceClass.APPARENT_POWER
#     ),
#     SensorEntityDescription(
#         key="charge",
#         name="ENCHARGE charging power",
#         native_unit_of_measurement=UnitOfPower.WATT,
#         state_class=SensorStateClass.MEASUREMENT,
#         device_class=SensorDeviceClass.POWER
#     ),
#     SensorEntityDescription(
#         key="discharge",
#         name="ENCHARGE discharging power",
#         native_unit_of_measurement=UnitOfPower.WATT,
#         state_class=SensorStateClass.MEASUREMENT,
#         device_class=SensorDeviceClass.POWER
#     ),
# )


ENCHARGE_INVENTORY_SENSORS = (
    SensorEntityDescription(
        key="encharge_capacity",
        name="Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="calculated_capacity",
        name="Calculated energy availiable",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    )
)


@dataclass(frozen=True, kw_only=True)
class EnsemblePowerSensorEntityDescription(SensorEntityDescription):
    """Provide a description of an ensemble power sensor."""

    value_fn: Callable[[EnchargePower], int | float]
    exists_fn: Callable[[dict], bool] = lambda _: True


ENSEMBLE_POWER_SENSORS = (
    EnsemblePowerSensorEntityDescription(
        key="soc",
        name="SoC",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda device: device.soc,
    ),
    EnsemblePowerSensorEntityDescription(
        key="apparent_power_mva",
        name="Apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        value_fn=lambda device: device.apparent_power_mva * 0.001,
    ),
    EnsemblePowerSensorEntityDescription(
        key="real_power_mw",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda device: device.real_power_mw * 0.001,
    ),
    EnsemblePowerSensorEntityDescription(
        key="charging_power_mw",
        name="Charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda device: device.charging_power * 0.001,
    ),
    EnsemblePowerSensorEntityDescription(
        key="discharging_power_mw",
        name="Discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda device: device.discharging_power * 0.001,
    ),
)


ENSEMBLE_AGG_POWER_SENSORS = (
    EnsemblePowerSensorEntityDescription(
        key="apparent_power_mva_agg",
        name="ENCHARGE apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        value_fn=lambda devices: devices.apparent_power_mva_agg * 0.001,
    ),
    EnsemblePowerSensorEntityDescription(
        key="real_power_mw_agg",
        name="ENCHARGE power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda devices: devices.real_power_mw_agg * 0.001,
    ),
    EnsemblePowerSensorEntityDescription(
        key="charging_power_mw_agg",
        name="ENCHARGE charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda devices: devices.charging_power_mw_agg * 0.001,
    ),
    EnsemblePowerSensorEntityDescription(
        key="discharging_power_mw_agg",
        name="ENCHARGE discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda devices: devices.discharging_power_mw_agg * 0.001,
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

    # Add the base sensors
    entities: list[Entity] = [
        GatewaySensorEntity(coordinator, description)
        for description in BASE_SENSORS
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

    # Add the ensemble aggregated power sensors
    if coordinator.data.ensemble_power:
        entities.extend(
            EnsembleAggregatedPowerEntity(coordinator, description)
            for description in ENSEMBLE_AGG_POWER_SENSORS
            if description.exists_fn(coordinator.data)
        )

    # Add the ensemble power sensors
    if coordinator.data.ensemble_power and conf_encharge_entity:
        entities.extend(
            EnsemblePowerEntity(coordinator, description)
            for description in ENSEMBLE_POWER_SENSORS
            if description.exists_fn(coordinator.data)
        )

    if coordinator.data.ensemble_secctrl:
        entities.extend(
            EnchargeAggregatedEntity(coordinator, description)
            for description in ENCHARGE_AGG_SENSORS
        )

    # if coordinator.data.ensemble_power:
    #     entities.extend(
    #         EnchargeAggregatedPowerEntity(coordinator, description)
    #         for description in ENCHARGE_AGG_POWER_SENSORS
    #     )

    if (data := coordinator.data.encharge_inventory) and conf_encharge_entity:
        entities.extend(
            EnchargeInventoryEntity(coordinator, description, encharge)
            for description in ENCHARGE_INVENTORY_SENSORS
            for encharge in data
        )

    # if (data := coordinator.data.encharge_power) and conf_encharge_entity:
    #     entities.extend(
    #         EnchargePowerEntity(coordinator, description, encharge)
    #         for description in ENCHARGE_POWER_SENSORS
    #         for encharge in data
    #     )

    _LOGGER.debug(f"Adding entities: {entities}")
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
        gateway = self.coordinator.data
        return self.entity_description.value_fn(gateway)


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
        self._attr_unique_id = f"{serial_number}_{description.key}"
        if as_device:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(self._serial_number))},
                name=f"Inverter {serial_number}",
                manufacturer="Enphase",
                model="Inverter",
                via_device=(DOMAIN, self.gateway_serial_num),
            )

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
    def native_value(self):
        """Return the state of the sensor."""
        ac_battery = self.data.ac_battery
        assert ac_battery is not None
        if ac_battery is None:
            return None

        return self.entity_description.value_fn(ac_battery)


class EnchargeAggregatedEntity(GatewaySensorEntity):
    """Aggregated Encharge entity."""

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        data = self.data.ensemble_secctrl
        if data is not None:
            return data.get(self.entity_description.key)

        return None


# class EnchargeAggregatedPowerEntity(GatewaySystemSensorEntity):
#     """Aggregated Encharge entity.

#     # FIXME
#     At the moment all devices of the power enpoint are aggregated.
#     There is no check if the device is an actual encharge device.
#     """

#     @property
#     def native_value(self) -> int:
#         """Return the state of the sensor."""
#         data = self.data.ensemble_power
#         if isinstance(data, list) and len(data) > 0:
#             real_power_agg = 0
#             apparent_power_agg = 0
#             for device in data:
#                 real_power_agg += device["real_power_mw"]
#                 apparent_power_agg += device["apparent_power_mva"]

#             if self.entity_description.key == "real_power_mw":
#                 return round(real_power_agg * 0.001)
#             elif self.entity_description.key == "apparent_power_mva":
#                 return round(apparent_power_agg * 0.001)
#             elif self.entity_description.key == "charge":
#                 power = round(real_power_agg * 0.001)
#                 return (power * -1) if power < 0 else 0
#             elif self.entity_description.key == "discharge":
#                 power = round(real_power_agg * 0.001)
#                 return power if power > 0 else 0

#         return None


class EnsembleAggregatedPowerEntity(GatewaySensorEntity):
    """Ensemble power aggregated entity."""

    entity_description: EnsemblePowerSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        ensemble_power = self.data.ensemle_power
        assert ensemble_power is not None
        if ensemble_power is not None:
            return self.entity_description.value_fn(ensemble_power)

        return None


class EnchargeEntity(GatewaySensorBaseEntity):
    """Encharge base entity."""

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


class EnchargeInventoryEntity(EnchargeEntity):
    """Ensemble inventory encharge data."""

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        inventory = self.data.encharge_inventory.get(self._serial_number)
        if inventory:
            if self.entity_description.key == "calculated_capacity":
                percentage = inventory.get("percentFull")
                capacity = inventory.get("encharge_capacity")
                if percentage and capacity:
                    return round(capacity * (percentage * 0.01))
            else:
                return inventory.get(self.entity_description.key)

        return None


class EnsemblePowerEntity(EnchargeEntity):
    """Ensemble power entity."""

    entity_description: EnsemblePowerSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        ensemble_power = self.data.ensemle_power
        assert ensemble_power is not None
        if ensemble_power is not None:
            return self.entity_description.value_fn(
                ensemble_power[self._serial_number]
            )

        return None
