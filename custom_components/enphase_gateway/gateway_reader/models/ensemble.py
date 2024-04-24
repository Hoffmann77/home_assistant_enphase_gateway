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


class EnsembleSecctrl:
    """Model for the ensemble/secctrl endpoint."""

    
    
    
    
    
    
    "shutdown": false,
    "freq_bias_hz": 0.13899999856948853,
    "voltage_bias_v": 1.6899999380111695,
    "freq_bias_hz_q8": 223,
    "voltage_bias_v_q5": 54,
    "freq_bias_hz_phaseb": 0.0,
    "voltage_bias_v_phaseb": 0.0,
    "freq_bias_hz_q8_phaseb": 0,
    "voltage_bias_v_q5_phaseb": 0,
    "freq_bias_hz_phasec": 0.0,
    "voltage_bias_v_phasec": 0.0,
    "freq_bias_hz_q8_phasec": 0,
    "voltage_bias_v_q5_phasec": 0,
    "configured_backup_soc": 0,
    "adjusted_backup_soc": 0,
    "agg_soc": 30,
    "Max_energy": 7000,
    "ENC_agg_soc": 30,
    "ENC_agg_soh": 98,
    "ENC_agg_backup_energy": 0,
    "ENC_agg_avail_energy": 2100,
    "Enc_commissioned_capacity": 7000,
    "Enc_max_available_capacity": 7000,
    "ACB_agg_soc": 0,
    "ACB_agg_energy": 0
    
    

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
    
    
    
    
