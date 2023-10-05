"""Experimental models."""


class BaseModel:
    """Base date model."""

    def __init__(self, data):
        self.data = data


class EnchargeInventory(BaseModel):
    """Inventory."""

    pass


class EnsembleSubmod(BaseModel):
    """Ensemble submod data."""

    pass
