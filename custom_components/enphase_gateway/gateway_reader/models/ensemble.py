"""Models for the Ensemble endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class EnsembleInventory:
    """Model for the Encharge/IQ Storage power endpoint."""

    percentFull: int
    temperature: int
    encharge_capacity: int

    @property
    def calculated_capacity(self):
        """Return the calculated capacity."""
        capacity = round(self.encharge_capacity * self.percentFull / 100)
        return capacity

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> EnsembleInventory:
        """Instantiate the model from the response."""
        return cls(
            percentFull=result["percentFull"],
            temperature=result["temperature"],
            encharge_capacity=result["encharge_capacity"],
        )

    def check(self, name: str) -> bool:
        """Check if the return value is valid."""
        value = getattr(self, name, None)
        if value is None:
            return False

        return True


@dataclass(slots=True)
class EnsemblePowerDevices:
    """Model for the Encharge/IQ Storage power endpoint."""

    devices: dict[str, EnsemblePower] = {}

    @property
    def apparent_power_mva_agg(self):
        """Return the aggregated real_power_mva."""
        power = 0
        for device in self.devices.values():
            power += device.apparent_power_mw

        return power

    @property
    def real_power_mw_agg(self):
        """Return the aggregated real_power_mw."""
        power = 0
        for device in self.devices.values():
            power += device.real_power_mw

        return power

    @property
    def charging_power_mw_agg(self):
        """Return the aggregated charging power."""
        if power := self.real_power_mw_agg is not None:
            return (power * -1) if power < 0 else 0

        return None

    @property
    def discharging_power_mw_agg(self):
        """Return the aggregated discharging power."""
        if power := self.real_power_mw_agg is not None:
            return power if power > 0 else 0

        return None

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> EnsemblePowerDevices:
        """Instantiate the model from the response."""
        devices = {
            device["serial_num"]: EnsemblePower.from_result(device)
            for device in result
        }

        return cls(devices=devices)

    def __getitem__(self, key) -> EnsemblePower:
        """Magic method."""
        return self.devices[key]

    def check(self, name: str) -> bool:
        """Check if the return value is valid."""
        value = getattr(self, name, None)
        if value is None:
            return False

        return True


@dataclass(slots=True)
class EnsemblePower:
    """Model for the Encharge/IQ battery power."""

    apparent_power_mva: int
    real_power_mw: int
    soc: int

    @property
    def charging_power_mw(self):
        """Return the charging power."""
        if power := self.real_power_mw is not None:
            return (power * -1) if power < 0 else 0

        return None

    @property
    def discharging_power_mw(self):
        """Return the discharging power."""
        if power := self.real_power_mw is not None:
            return power if power > 0 else 0

        return None

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> EnsemblePower:
        """Instantiate the model from the response."""
        return cls(
            apparent_power_mva=result["apparent_power_mva"],
            real_power_mw=result["real_power_mw"],
            soc=result["soc"],
        )

    def check(self, name: str) -> bool:
        """Check if the return value is valid."""
        value = getattr(self, name, None)
        if value is None:
            return False

        return True
