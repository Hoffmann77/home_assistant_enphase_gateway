"""Home assistant base entities."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityDescription

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
        return self.coordinator.data
