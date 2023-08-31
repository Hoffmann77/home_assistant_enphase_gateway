

from ..descriptors import JsonDescriptor


class BaseModel:
    """Base date model."""
    
    def __init__(self, data):
        self.data = data


class ACBattery(BaseModel):
    """AC battery data."""
    
    percentFull = JsonDescriptor("percentFull")
    
    wNow = JsonDescriptor("wNow")
    
    whNow = JsonDescriptor("whNow")
    
    state = JsonDescriptor("state")
    
    
    
    
    
    
    
        
    
    
        
        
    