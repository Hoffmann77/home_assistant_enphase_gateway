# -*- coding: utf-8 -*-
"""
Created on Sat Feb 24 19:45:20 2024

@author: Bobby
"""

class ShemaGenerator:
    """Class for generating a input shema."""
    
    
    def get_shema(self, name, default=None):
        func = getattr(self, f"get_{name}_shema")
        return func(default)
 




    def get_inverter_shema(default):
        """Return the inverter shema."""
        key = vol.Optional(CONF_INVERTERS, default=default)
        val = selector(
            {
                "select": {
                    "translation_key": CONF_INVERTERS,
                    "mode": "dropdown",
                    "options": ["gateway_sensor", "device", "disabled"],
                }
            }
        )
        
        return {key: val}
        
        