"""Model for the legacy Enphase AC Battery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# from ..descriptors import JsonDescriptor
# from .common import BaseModel


@dataclass(slots=True)
class ACBatteryStorage:
    """Model for the legacy Enphase AC Battery."""

    percentFull = int
    whNow = int
    wNow = int
    state = str

    @property
    def charging_power(self):
        """Return the charging power."""
        if power := self.wNow is not None:
            return (power * -1) if power < 0 else 0

        return None

    @property
    def discharging_power(self):
        """Return the discharging power."""
        if power := self.wNow is not None:
            return power if power > 0 else 0

        return None

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> ACBatteryStorage:
        """Instantiate class from response."""
        return cls(
            percentFull=result["percentFull"],
            whNow=result["whNow"],
            wNow=result["wNow"],
            state=result["state"],
        )

    def check(self, name: str) -> bool:
        """Check if the return value is valid."""
        value = getattr(self, name, None)
        if value is None:
            return False

        return True
