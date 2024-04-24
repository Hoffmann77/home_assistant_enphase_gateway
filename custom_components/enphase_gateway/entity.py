"""Home assistant base entities."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityDescription
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity

from .coordinator import GatewayReaderUpdateCoordinator
from .coordinator import GatewayCoordinator


class GatewayCoordinatorEntity(CoordinatorEntity[GatewayCoordinator]):
    """Coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            coordinator: GatewayCoordinator,
            description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.gateway_serial_num = coordinator.gateway_reader.serial_number

    @property
    def data(self) -> dict:
        """Return the gateway data."""
        data = self.coordinator.data
        return data



class GatewayBaseEntity(CoordinatorEntity[GatewayReaderUpdateCoordinator]):
    """Defines a base gateway entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            coordinator: GatewayReaderUpdateCoordinator,
            description: EntityDescription,
    ) -> None:
        """Initialize the gateway base entity."""
        self.entity_description = description
        self.gateway_serial_num = coordinator.gateway_reader.serial_number
        super().__init__(coordinator)

    @property
    def data(self) -> dict:
        """Return the gateway data."""
        data = self.coordinator.data
        return data


class GatewaySensorBaseEntity(GatewayBaseEntity, SensorEntity):
    """Defines a base gateway sensor entity."""

    pass


class GatewayBinarySensorBaseEntity(GatewayBaseEntity, BinarySensorEntity):
    """Defines a base envoy binary_sensor entity."""

    pass
