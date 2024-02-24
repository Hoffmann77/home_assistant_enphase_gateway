"""Model for the legacy Enphase AC Battery."""

from dataclasses import dataclass

# from ..descriptors import JsonDescriptor
# from .common import BaseModel


@dataclass(slots=True)
class AcBattery:
    """Model for the legacy Enphase AC Battery."""

    # percentFull = JsonDescriptor("percentFull")
    percentFull = int
    whNow = int
    wNow = int
    state = str

    @property
    def charging_power(self):
        """Return the charging power."""
        if power := self.wNow is not None:
            return (power * -1) if power < 0 else 0

    @property
    def discharging_power(self):
        """Return the discharging power."""
        if power := self.wNow is not None:
            return power if power > 0 else 0

    @classmethod
    def from_response(cls, response):
        """Instantiate class from response."""
        return cls(
            percentFull=response["percentFull"],
            whNow=response["whNow"],
            wNow=response["wNow"],
            state=response["state"],
        )
