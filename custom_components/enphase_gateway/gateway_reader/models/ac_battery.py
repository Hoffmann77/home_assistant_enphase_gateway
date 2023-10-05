"""Models."""

# from ..descriptors import JsonDescriptor


class BaseModel:
    """Base date model."""

    def __init__(self, data):
        self.data = data

    def register_property(x, y):
        """Register property."""
        pass


class ACBattery(BaseModel):
    """AC battery data."""

    # percentFull = JsonDescriptor("percentFull")

    # wNow = JsonDescriptor("wNow")

    # whNow = JsonDescriptor("whNow")

    # state = JsonDescriptor("state")
