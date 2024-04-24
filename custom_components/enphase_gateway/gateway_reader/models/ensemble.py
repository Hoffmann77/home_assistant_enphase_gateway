"""Models for the Ensemble endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class EnchargePower:
    """Model for the Encharge/IQ battery power."""

    apparent_power_mva: int
    real_power_mw: int
    soc: int

    @property
    def charging_power(self):
        """Return the charging power."""
        if power := self.real_power_mw is not None:
            return (power * -1) if power < 0 else 0

        return None

    @property
    def discharging_power(self):
        """Return the discharging power."""
        if power := self.real_power_mw is not None:
            return power if power > 0 else 0

        return None

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> EnchargePower:
        """Instantiate class from the response."""
        return cls(
            apparent_power_mva=response["apparent_power_mva"],
            real_power_mw=response["real_power_mw"],
            soc=response["soc"],
        )
