"""Home assistant sensors for the Enphase gateway integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfEnergy,
    UnitOfPower,
)

from .const import DOMAIN,  ICON
from .entity import GatewaySensorBaseEntity
from .coordinator import EnphaseUpdateCoordinator





INVERTER_SENSORS = (
    SensorEntityDescription(
        key="lastReportWatts",
        name="Inverter",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # !!!: can be used for a seperate devices for every inverter
    # EnvoyInverterSensorEntityDescription(
    #     key=LAST_REPORTED_KEY,
    #     translation_key=LAST_REPORTED_KEY,
    #     device_class=SensorDeviceClass.TIMESTAMP,
    #     entity_registry_enabled_default=False,
    #     value_fn=lambda inverter: dt_util.utc_from_timestamp(inverter.last_report_date),
    # ),
)


PRODUCTION_SENSORS = (
    SensorEntityDescription(
        key="production",
        name="Current Power Production",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        #value_fn=lambda production: production.watts_now,
    ),
    SensorEntityDescription(
        key="daily_production",
        name="Today's Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        #value_fn=lambda production: production.watt_hours_today,
    ),
    SensorEntityDescription(
        key="seven_days_production",
        name="Last Seven Days Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="lifetime_production",
        name="Lifetime Energy Production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
    ),
)    


CONSUMPTION_SENSORS = (
    SensorEntityDescription(
        key="consumption",
        name="Current Power Consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        #value_fn=lambda consumption: consumption.watts_now,
    ),
    SensorEntityDescription(
        key="daily_consumption",
        name="Today's Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        #value_fn=lambda consumption: consumption.watt_hours_today,
    ),
    SensorEntityDescription(
        key="seven_days_consumption",
        name="Last Seven Days Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="lifetime_consumption",
        name="Lifetime Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
    ),
)


AC_BATTERY_SENSORS = (
    SensorEntityDescription(
        key="whNow",
        name="AC-Battery Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
    SensorEntityDescription(
        key="percentFull",
        name="AC-Battery Soc",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY
    ),
    SensorEntityDescription(
        key="wNow",
        name="AC-Battery power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
    SensorEntityDescription(
        key="charge",
        name="AC-Battery charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
    SensorEntityDescription(
        key="discharge",
        name="AC-Battery discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
)


ENCHARGE_AGG_SENSORS = (
    SensorEntityDescription(
        key="Enc_max_available_capacity",
        name="Encharge array nominal capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
    SensorEntityDescription(
        key="ENC_agg_avail_energy",
        name="Encharge array capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
    SensorEntityDescription(
        key="ENC_agg_backup_energy",
        name="Encharge array backup capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
    SensorEntityDescription(
        key="ENC_agg_soc",
        name="Encharge array Soc",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY
    ),
    SensorEntityDescription(
        key="ENC_agg_soh",
        name="Encharge array Soh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


ENCHARGE_AGG_POWER_SENSORS = (
    SensorEntityDescription(
        key="real_power_mw",
        name="Encharge power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
    SensorEntityDescription(
        key="apparent_power_mva",
        name="Apparent power",
        native_unit_of_measurement=UnitOfApparentPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER
    ),
    SensorEntityDescription(
        key="charge",
        name="Encharge charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
    SensorEntityDescription(
        key="discharge",
        name="Encharge discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
)


ENCHARGE_INVENTORY_SENSORS = (
    SensorEntityDescription(
        key="encharge_capacity",
        name="Nominal Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE
    ),
)


ENCHARGE_POWER_SENSORS = (
    SensorEntityDescription(
        key="calculated_capacity",
        name="Calculated capacity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY
    ),
    SensorEntityDescription(
        key="soc",
        name="State of charge",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY
    ),
    SensorEntityDescription(
        key="real_power_mw",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
    SensorEntityDescription(
        key="apparent_power_mva",
        name="Apparent power",
        native_unit_of_measurement=UnitOfApparentPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER
    ),
    SensorEntityDescription(
        key="charge",
        name="Current charging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
    SensorEntityDescription(
        key="discharge",
        name="Current discharging power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER
    ),
)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up envoy sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    
    for sensor_description in (PRODUCTION_SENSORS + CONSUMPTION_SENSORS):
        if getattr(coordinator.data, sensor_description.key):
            entities.append(
                GatewaySensorEntity(coordinator, sensor_description)
            )
      
    if data := coordinator.data.inverters_production:
        entities.extend(
            GatewayInverterEntity(coordinator, description, inverter)
            for description in INVERTER_SENSORS
            for inverter in data
        )

    elif coordinator.data.ensemble_secctrl:
        entities.extend(
            EnchargeAggregatedEntity(coordinator, description)
            for description in ENCHARGE_AGG_SENSORS
        )

    elif coordinator.data.ensemble_power:
        entities.extend(
            EnchargeAggregatedPowerEntity(coordinator, description)
            for description in ENCHARGE_AGG_POWER_SENSORS
        )
    
    elif data := coordinator.data.encharge_inventory:
        entities.extend(
            EnchargeInventoryEntity(coordinator, description, encharge)
            for description in ENCHARGE_INVENTORY_SENSORS
            for encharge in data
        )
        
    elif data := coordinator.data.encharge_power:
        entities.extend(
            EnchargePowerEntity(coordinator, description, encharge)
            for description in ENCHARGE_POWER_SENSORS
            for encharge in data
        )
    
    async_add_entities(entities)

        
class GatewaySystemSensorEntity(GatewaySensorBaseEntity):
    """Gateway system base entity."""

    _attr_icon = ICON

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Envoy entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{self.gateway_serial_num}_{description.key}"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self.gateway_serial_num))},
            name=self.coordinator.name,
            manufacturer="Enphase",
            model=self.coordinator.gateway_reader.name,
            sw_version=self.coordinator.gateway_reader.firmware_version,
        )
        

class GatewaySensorEntity(GatewaySystemSensorEntity):
    """Gateway sensor entity."""
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
        

class GatewayInverterEntity(GatewaySystemSensorEntity): # or GatewaySensorBaseEntity
    """Gateway inverter entity."""

    _attr_icon = ICON

    def __init__(
            self,
            coordinator,
            description,
            serial_number: str,
    ) -> None:
        """Initialize Gateway inverter entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        self._attr_unique_id = serial_number

    # @property
    # def device_info(self) -> DeviceInfo:
    #     """Return the device_info of the device."""
    #     return DeviceInfo(
    #         identifiers={(DOMAIN, str(self._serial_number))},
    #         name=f"Inverter {self._serial_number}",
    #         manufacturer="Enphase",
    #         model="Inverter",
    #         via_device=(DOMAIN, self.gateway_serial_num),
    #     )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.data.get("inverters_production")
        if data != None:
            inv = data.get(self._serial_number)
            return inv.get(self.entity_description.key) if inv else None
            
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = self.data.get("inverters_production")
        if data != None:
            inv = data.get(self._serial_number)
            if last_reported := inv.get("last_reported"):
                return dt_util.utc_from_timestamp(last_reported)
            
        return None


class ACBatteryEntity(GatewaySystemSensorEntity):
    """AC battery entity."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        storage = self.data.acb_storage
        if self.entity_description.key in {"charge", "discharge"}:
            if power := storage.get("wNow") != None:
                if self.entity_description.key == "charge":
                    return (power * -1) if power < 0 else 0    
                elif self.entity_description.key == "discharge":
                    return power if power > 0 else 0  
        else:
            return storage.get(self.entity_description.key)
        
        return None

    
class EnchargeAggregatedEntity(GatewaySystemSensorEntity):
    """Aggregated Encharge entity."""

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        data = self.data.ensemble_secctrl
        if data != None:
            return data.get(self.entity_description.key)
        
        return None


class EnchargeAggregatedPowerEntity(GatewaySystemSensorEntity):
    """Aggregated Encharge entity.
    
    # FIXME
    At the moment all devices of the power enpoint are aggregated.
    There is no check if the device is an actual encharge device.
    """

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        data = self.data.ensemble_power
        if type(data, list) and len(data) > 0:
            real_power_agg = 0
            apparent_power_agg = 0
            for device in data:
                real_power_agg += device["real_power_mw"]
                apparent_power_agg += device["real_power_mva"]
            
            if self.entity_description.key == "real_power_mw":
                return round(real_power_agg * 0.001)
            elif self.entity_description.key == "real_power_mva":
                return round(apparent_power_agg * 0.001)
            elif self.entity_description.key == "charge":
                power = round(real_power_agg * 0.001)
                return (power * -1) if power < 0 else 0 
            elif self.entity_description.key == "discharge":
                power = round(real_power_agg * 0.001)
                return power if power > 0 else 0 
                
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
            via_device=(DOMAIN, self._gateway_serial_num)
        )
    
    
class EnchargeInventoryEntity(EnchargeEntity):
    """Ensemble inventory encharge data."""
    
    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        storage = self.data.encharge_inventory.get(self._serial_number)
        if storage:
            return storage.get(self.entity_description.key)
            
        return None

             
class EnchargePowerEntity(EnchargeEntity):
    """Ensemble power data."""
    
    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        storage = self.data.encharge_power.get(self._serial_number)
        if storage:
            if self.entity_description.key == "calculated_capacity":
                percentage = storage.get("percentFull")
                capacity = storage.get("encharge_capacity")
                if percentage and capacity:
                    return round(capacity * (percentage *0.01))
            
            elif self.entity_description.key == "real_power_mw":
                if real_power := storage.get("real_power_mw") != None:
                    return round(real_power * 0.001)
                
            elif self.entity_description.key == "apparent_power_mva":
                if apparent_power := storage.get("apparent_power_mva") != None:
                    return round(apparent_power * 0.001)

            elif self.entity_description.key == "charge":
                if real_power := storage.get("real_power_mw") != None:
                    real_power = round(real_power * 0.001)
                    return (real_power * -1) if real_power < 0 else 0
                
            elif self.entity_description.key == "discharge":
                if real_power := storage.get("real_power_mw") != None:
                    real_power = round(real_power * 0.001)
                    return real_power if real_power > 0 else 0
        
        return None
    


        


# class CoordinatedGatewayEntity(SensorEntity, CoordinatorEntity):
#     """Enphase gateway entity."""
    
#     def __init__(
#             self,
#             description,
#             entity_name,
#             serial_number,
#             device_name,
#             device_serial_number,
#             coordinator,
#     ):
#         """Initialize the Enphase gateway entity."""
#         self.entity_description = description
#         self._entity_name = entity_name
#         self._serial_number = serial_number
#         self._device_name = device_name
#         self._device_serial_number = device_serial_number
#         CoordinatorEntity.__init__(self, coordinator)

#     @property
#     def name(self):
#         """Return the name of the sensor entity."""
#         return self._entity_name

#     @property
#     def unique_id(self):
#         """Return the unique_id of the sensor entity."""
#         if self._serial_number:
#             return self._serial_number
#         if serial := self._device_serial_number:
#             return f"{serial}_{self.entity_description.key}"

#     @property
#     def icon(self):
#         """Icon to use in the frontend, if any."""
#         return ICON

#     @property
#     def extra_state_attributes(self):
#         """Return the state attributes."""
#         return None
    
#     @property
#     def device_info(self) -> DeviceInfo | None:
#         """Return the device_info of the device."""
#         if not self._device_serial_number:
#             return None
#         gateway_type = None
#         if info := self.coordinator.data.get("gateway_info"):
#             gateway_type = info.get("gateway_type", "Gateway")
        
#         return DeviceInfo(
#             identifiers={(DOMAIN, str(self._device_serial_number))},
#             manufacturer="Enphase",
#             model=gateway_type or "Gateway",
#             name=self._device_name,
#         )
    
#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         return self.coordinator.data.get(self.entity_description.key)
        


# class GatewayInverterEntity(CoordinatedGatewayEntity):
#     """Gateway Inverter entity."""

#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         if inv_prod := self.coordinator.data.get("inverters_production"):
#             return inv_prod.get(self._serial_number)[0]
#         return None

#     @property
#     def extra_state_attributes(self):
#         """Return the state attributes."""
#         if inv_prod := self.coordinator.data.get("inverters_production"):
#             value = inv_prod.get(self._serial_number)[1]
#             return {"last_reported": value}
#         return None        
        



# class GatewayBatteryEntity(CoordinatedGatewayEntity):
#     """Gateway Battery entity."""

#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         if storages := self.coordinator.data.get("batteries"):
#             return storages.get(self._serial_number).get("percentFull")
#         return None

#     @property
#     def extra_state_attributes(self):
#         """Return the state attributes."""
#         if storages := self.coordinator.data.get("batteries").get("ENCHARGE"):
#             storage = storages.get(self._serial_number)
#             last_reported = strftime(
#                 "%Y-%m-%d %H:%M:%S", localtime(storage.get("last_rpt_date"))
#             )
#             return {
#                 "last_reported": last_reported,
#                 "capacity": storage.get("encharge_capacity")
#             }
#         return None





# class TotalBatteryPowerEntity(CoordinatedGatewayEntity):
    
#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         ensemble_power = self.coordinator.data.get("ensemble_power", {})
#         ensemble_power = {item["serial_num"]: item for item in ensemble_power}
        
#         if storages := self.coordinator.data.get("batteries"):
#             total_power = 0
#             for uid, storage in storages.items():
#                 if uid.startswith("acb"):
#                     total_power += storage.get("wNow")
#                 elif uid.startswith("encharge"):
#                     serial_num = storage["serial_num"]
#                     if ensemble_power:
#                         device = ensemble_power[serial_num]
#                         power = round(device.get("real_power_mw", 0) / 1000)
#                         total_power += power
#             return total_power    
#         else:
#             return None
            
            
            

    
    
# class TotalBatteryCapacityEntity(CoordinatedGatewayEntity):
#     """Total capacity entity."""
    
#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         ensemble_secctrl = self.coordinator.data.get("ensemble_secctrl")
        
#         if storages := self.coordinator.data.get("batteries"):
#             encharge_finished = False
#             total = 0
#             for uid, storage in storages.items():
#                 if uid.startswith("acb"):
#                     total += storage.get("whNow", 0)
#                 elif uid.startswith("encharge"):
#                     if ensemble_secctrl and not encharge_finished:
#                         agg = ensemble_secctrl.get("ENC_agg_avail_energy", 0)
#                         total += agg
#                         encharge_finished = True
#                     elif not encharge_finished:
#                         percentage = storage.get("percentFull")
#                         capacity = storage.get("encharge_capacity")
#                         total += round(capacity * (percentage / 100.0))
#             return total
#         return None


# class TotalBatteryPercentageEntity(CoordinatedGatewayEntity):
#     """Total battery percentage entity."""
    
#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         ensemble_secctrl = self.coordinator.data.get("ensemble_secctrl")
#         if storages := self.coordinator.data.get("batteries"):
#             curr_capacity = 0
#             total_capacity = 0
#             if ensemble_secctrl:
#                 if soc := ensemble_secctrl.get("agg_soc"):
#                     return soc
#             for uid, storage in storages.items():
#                 if uid.startswith("acb"):
#                     percentage = storage.get("percentFull")
#                     curr_capacity += round(1280 * (percentage / 100.0))
#                     total_capacity += 1280
#                 elif uid.startswith("encharge"):
#                     percentage = storage.get("percentFull")
#                     capacity = storage.get("encharge_capacity")
#                     curr_capacity += round(capacity * (percentage / 100.0))
#                     total_capacity += capacity    
#             return round((curr_capacity / total_capacity) * 100)
#         return None
                







# class EnchargeEntity(SensorEntity, CoordinatorEntity):
#     """Encharge storage entitiy."""
    
#     def __init__(
#             self,
#             description,
#             entity_name,
#             serial_number,
#             device_name,
#             device_serial_number,
#             parent_device,
#             coordinator,
#     ):
#         """Initialize the Encharge storage entity."""
#         self.entity_description = description
#         self._entity_name = entity_name
#         self._serial_number = serial_number
#         self._device_name = device_name
#         self._device_serial_number = device_serial_number
#         self._parent_device = parent_device
#         CoordinatorEntity.__init__(self, coordinator)

#     @property
#     def name(self):
#         """Return the name of the sensor entity."""
#         return self._entity_name

#     @property
#     def icon(self):
#         """Icon to use in the frontend, if any."""
#         return ICON

#     @property
#     def unique_id(self):
#         """Return the unique id of the sensor."""
#         if self._serial_number:
#             return self._serial_number
#         if serial := self._device_serial_number:
#             return f"{serial}_{self.entity_description.key}"
     
#     @property
#     def device_info(self) -> DeviceInfo | None:   
#         """Return the device_info of the device."""
#         return DeviceInfo(
#             identifiers={(DOMAIN, str(self._device_serial_number))},
#             manufacturer="Enphase",
#             model="Encharge",
#             name=self._device_name,
#             via_device=(DOMAIN, self._parent_device)
#         )
    
#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         if storages := self.coordinator.data.get("encharge"):
#             storage = storages.get(self._device_serial_number)
            
#             if self.entity_description.key == "current_capacity":
#                 percentage = storage.get("percentFull")
#                 capacity = storage.get("encharge_capacity")
#                 if percentage and capacity:
#                     return round(capacity * (percentage / 100.0))
            
#             elif self.entity_description.key == "real_power_mw":
#                 if real_power := storage.get("real_power_mw") != None:
#                     return round(real_power / 1000)

#             elif self.entity_description.key == "charge":
#                 if real_power := storage.get("real_power_mw") != None:
#                     real_power = round(real_power / 1000)
#                     return (real_power * -1) if real_power < 0 else 0
                
#             elif self.entity_description.key == "discharge":
#                 if real_power := storage.get("real_power_mw") != None:
#                     real_power = round(real_power / 1000)
#                     return real_power if real_power > 0 else 0
            
#             else:
#                 return storage.get(self.entity_description.key)
            
#         return None

#     @property
#     def extra_state_attributes(self):
#         """Return the state attributes."""
#         if storages := self.coordinator.data.get("encharge"):
#             storage = storages.get(self._device_serial_number)
#             if last_reported := storage.get("last_rpt_date"):
#                 return {
#                     "last_reported": strftime(
#                         "%Y-%m-%d %H:%M:%S", localtime(last_reported)
#                     )
#                 }
            
#         return None

