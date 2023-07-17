"""Sensor entities for Enphase gateway integration."""
from __future__ import annotations

from time import strftime, localtime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BATTERY_ENERGY_DISCHARGED_SENSOR, BATTERY_ENERGY_CHARGED_SENSOR, 
    COORDINATOR, DOMAIN, NAME, SENSORS, ENCHARGE_SENSORS, ICON
)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback) -> None:
    """Set up envoy sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data[COORDINATOR]
    device_name = data[NAME]
    entities = []
    
    for sensor_description in SENSORS:
        if sensor_description.key == "inverters":
            if inverters := coordinator.data.get("inverters_production"):
                for inverter in inverters:
                    entity_name = (
                        f"{device_name} {sensor_description.name} {inverter}"    
                    )
                    entities.append(
                        GatewayInverterEntity(
                            description=sensor_description,
                            entity_name=entity_name,
                            serial_number=inverter,
                            device_name=device_name,
                            device_serial_number=config_entry.unique_id,
                            coordinator=coordinator,
                        )
                    )
        
        elif sensor_description.key == "batteries":
            if storages := coordinator.data.get("batteries").get("ENCHARGE"):
                for storage in storages:
                    entity_name = (
                        f"{device_name} {sensor_description.name} {storage}"
                    )
                    entities.append(
                        GatewayBatteryEntity(
                            description=sensor_description,
                            entity_name=entity_name,
                            serial_number=storage,
                            device_name=device_name,
                            device_serial_number=config_entry.unique_id,
                            coordinator=coordinator
                        )
                    )

        elif sensor_description.key == "current_battery_capacity":
            if coordinator.data.get("batteries"):
                battery_capacity_entity = TotalBatteryCapacityEntity(
                    description=sensor_description,
                    entity_name=f"{device_name} {sensor_description.name}",
                    serial_number=None,
                    device_name=device_name,
                    device_serial_number=config_entry.unique_id,
                    coordinator=coordinator
                )
                entities.append(battery_capacity_entity)

                # entities.append(
                #     BatteryEnergyChangeEntity(
                #         BATTERY_ENERGY_CHARGED_SENSOR,
                #         f"{device_name} {BATTERY_ENERGY_CHARGED_SENSOR.name}",
                #         device_name,
                #         config_entry.unique_id,
                #         None,
                #         battery_capacity_entity,
                #         True
                #     )
                # )

                # entities.append(
                #     BatteryEnergyChangeEntity(
                #         BATTERY_ENERGY_DISCHARGED_SENSOR,
                #         f"{device_name} {BATTERY_ENERGY_DISCHARGED_SENSOR.name}",
                #         device_name,
                #         config_entry.unique_id,
                #         None,
                #         battery_capacity_entity,
                #         False
                #     )
                # )

        elif sensor_description.key == "total_battery_percentage":
            if coordinator.data.get("batteries"):
                entities.append(
                    TotalBatteryPercentageEntity(
                        description=sensor_description,
                        entity_name=f"{device_name} {sensor_description.name}",
                        serial_number=None,
                        device_name=device_name,
                        device_serial_number=config_entry.unique_id,
                        coordinator=coordinator
                    )
                )

        else:
            data = coordinator.data.get(sensor_description.key)
            if isinstance(data, str) and "not available" in data:
                continue
            entities.append(
                CoordinatedGatewayEntity(
                    description=sensor_description,
                    entity_name=f"{device_name} {sensor_description.name}",
                    serial_number=None,
                    device_name=device_name,
                    device_serial_number=config_entry.unique_id,
                    coordinator=coordinator
                )
            )

    for sensor_description in ENCHARGE_SENSORS:
        if storages := coordinator.data.get("encharge"):
            for storage in storages:
                device_name = f"Encharge {storage}"
                entity_name = f"{device_name} {sensor_description.name}"
                # if not sensor_description.key in storages[storage].keys():
                #     if sensor_description.key in {"charge", "discharge"}:
                #         pass
                #     else:
                #         continue
                entities.append(
                    EnchargeEntity(
                        description=sensor_description,
                        entity_name=entity_name,
                        serial_number=None,
                        device_name=device_name,
                        device_serial_number=storage,
                        parent_device=config_entry.unique_id,
                        coordinator=coordinator,
                    )
                )
    
    async_add_entities(entities)


class CoordinatedGatewayEntity(SensorEntity, CoordinatorEntity):
    """Enphase gateway entity."""
    
    def __init__(
            self,
            description,
            entity_name,
            serial_number,
            device_name,
            device_serial_number,
            coordinator,
    ):
        """Initialize the Enphase gateway entity."""
        self.entity_description = description
        self._entity_name = entity_name
        self._serial_number = serial_number
        self._device_name = device_name
        self._device_serial_number = device_serial_number
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def name(self):
        """Return the name of the sensor entity."""
        return self._entity_name

    @property
    def unique_id(self):
        """Return the unique_id of the sensor entity."""
        if self._serial_number:
            return self._serial_number
        if serial := self._device_serial_number:
            return f"{serial}_{self.entity_description.key}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return None
    
    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device_info of the device."""
        if not self._device_serial_number:
            return None
        
        if info := self.coordinator.data.get("gateway_info"):
            gateway_type = info.get("gateway_type", "Gateway")
        
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_serial_number))},
            manufacturer="Enphase",
            model=gateway_type or "Gateway",
            name=self._device_name,
        )
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
        

class GatewayInverterEntity(CoordinatedGatewayEntity):
    """Gateway Inverter entity."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if inv_prod := self.coordinator.data.get("inverters_production"):
            return inv_prod.get(self._serial_number)[0]
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if inv_prod := self.coordinator.data.get("inverters_production"):
            value = inv_prod.get(self._serial_number)[1]
            return {"last_reported": value}
        return None        
        

class GatewayBatteryEntity(CoordinatedGatewayEntity):
    """Gateway Battery entity."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if storages := self.coordinator.data.get("batteries").get("ENCHARGE"):
            return storages.get(self._serial_number).get("percentFull")
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if storages := self.coordinator.data.get("batteries").get("ENCHARGE"):
            storage = storages.get(self._serial_number)
            last_reported = strftime(
                "%Y-%m-%d %H:%M:%S", localtime(storage.get("last_rpt_date"))
            )
            return {
                "last_reported": last_reported,
                "capacity": storage.get("encharge_capacity")
            }
        return None


class TotalBatteryCapacityEntity(CoordinatedGatewayEntity):
    """Total capacity entity."""
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if storages := self.coordinator.data.get("batteries").get("ENCHARGE"):
            total = 0
            for storage in storages.values():
                percentage = storage.get("percentFull")
                capacity = storage.get("encharge_capacity")
                total += round(capacity * (percentage / 100.0))
            return total
        return None


class TotalBatteryPercentageEntity(CoordinatedGatewayEntity):
    """Total battery percentage entity."""
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if storages := self.coordinator.data.get("batteries").get("ENCHARGE"):
            curr_capacity = 0
            total_capacity = 0
            for storage in storages.values():
                percentage = storage.get("percentFull")
                capacity = storage.get("encharge_capacity")
                curr_capacity += round(capacity * (percentage / 100.0))
                total_capacity += capacity
            return round((curr_capacity / total_capacity) * 100)
        return None        


class EnchargeEntity(SensorEntity, CoordinatorEntity):
    """Encharge storage entitiy."""
    
    def __init__(
            self,
            description,
            entity_name,
            serial_number,
            device_name,
            device_serial_number,
            parent_device,
            coordinator,
    ):
        """Initialize the Encharge storage entity."""
        self.entity_description = description
        self._entity_name = entity_name
        self._serial_number = serial_number
        self._device_name = device_name
        self._device_serial_number = device_serial_number
        self._parent_device = parent_device
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def name(self):
        """Return the name of the sensor entity."""
        return self._entity_name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        if self._serial_number:
            return self._serial_number
        if serial := self._device_serial_number:
            return f"{serial}_{self.entity_description.key}"
     
    @property
    def device_info(self) -> DeviceInfo | None:   
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_serial_number))},
            manufacturer="Enphase",
            model="Encharge",
            name=self._device_name,
            via_device=(DOMAIN, self._parent_device)
        )
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if storages := self.coordinator.data.get("encharge"):
            storage = storages.get(self._device_serial_number)
            
            if self.entity_description.key == "current_capacity":
                percentage = storage.get("percentFull")
                capacity = storage.get("encharge_capacity")
                if percentage and capacity:
                    return round(capacity * (percentage / 100.0))
            
            elif self.entity_description.key == "real_power_mw":
                if real_power := storage.get("real_power_mw"):
                    return round(real_power / 1000)

            elif self.entity_description.key == "charge":
                if real_power := storage.get("real_power_mw"):
                    real_power = round(real_power / 1000)
                    return real_power if real_power > 0 else 0
                
            elif self.entity_description.key == "discharge":
                if real_power := storage.get("real_power_mw"):
                    real_power = round(real_power / 1000)
                    return real_power if real_power < 0 else 0
            
            else:
                return storage.get(self.entity_description.key)
            
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if storages := self.coordinator.data.get("encharge"):
            storage = storages.get(self._device_serial_number)
            if last_reported := storage.get("last_rpt_date"):
                return {
                    "last_reported": strftime(
                        "%Y-%m-%d %H:%M:%S", localtime(last_reported)
                    )
                }
            
        return None


# class BatteryEnergyChangeEntity(GatewayEntity):
#     """Battery energy change entity."""
    
#     def __init__(
#             self,
#             description,
#             name,
#             device_name,
#             device_serial_number,
#             serial_number,
#             total_battery_capacity_entity,
#             positive: bool
#     ):
#         super().__init__(
#             description=description,
#             name=name,
#             device_name=device_name,
#             device_serial_number=device_serial_number,
#             serial_number=serial_number,
#         )
#         self._sensor_source = total_battery_capacity_entity
#         self._positive = positive
#         self._state = 0
#         self._attr_last_reset = datetime.datetime.now()

#     async def async_added_to_hass(self):
#         """Handle entity which will be added."""
#         await super().async_added_to_hass()

#         @callback
#         def calc_change(event):
#             """Handle the sensor state changes."""
#             old_state = event.data.get("old_state")
#             new_state = event.data.get("new_state")

#             if (
#                 old_state is None
#                 or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
#                 or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
#             ):
#                 self._state = 0

#             else:
#                 old_state_value = int(old_state.state)
#                 new_state_value = int(new_state.state)

#                 if (self._positive):
#                     if (new_state_value > old_state_value):
#                         self._state = new_state_value - old_state_value
#                     else:
#                         self._state = 0

#                 else:
#                     if (old_state_value > new_state_value):
#                         self._state = old_state_value - new_state_value
#                     else:
#                         self._state = 0

#             self._attr_last_reset = datetime.datetime.now()
#             self.async_write_ha_state()

#         self.async_on_remove(
#             async_track_state_change_event(
#                 self.hass, self._sensor_source.entity_id, calc_change
#             )
#         )

#     @property
#     def native_value(self):
#         """Return the state of the sensor."""
#         return self._state
