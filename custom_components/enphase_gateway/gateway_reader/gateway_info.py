"""Gateway info reader."""

import httpx
import time
from awesomeversion import AwesomeVersion
from datetime import datetime, timezone, timedelta
from lxml import etree

from .http import async_get
from .exceptions import EnvoyFirmwareCheckError, EnvoyFirmwareFatalCheckError, GatewayCommunicationError


class GatewayInfo:
    """Class representing the gateway info endpoint.

    Attribues
    ---------
    part_number : str or None
        Gateway part number.
    serial_number : str or None
        Gateway serial number.
    firmware_version : AwesomeVersion or None.
        Gateway firmware version.
    imeter : bool
        Gateway imeter value.
    web_tokens : bool
        Gateway web_tokens value.
    populated : bool
        If instance is populated.
    
    Raises
    ------
    
    
    
    
    """

    def __init__(self, host: str, async_client: httpx.AsyncClient) -> None:
        """Initialize GatewayInfo."""
        self._host = host
        self._async_client = async_client
        self.part_number: str | None = None
        self.serial_number: str | None = None
        self.firmware_version: AwesomeVersion | None = None
        self.imeter: bool = False
        self.web_tokens: bool = False
        self.populated: bool = False
        self._last_fetch: float | None = None

    @property
    def update_required(self) -> bool:
        """Return if an update of the info endpoint is required."""
        if not self.populated or self._last_fetch + 86000 <= time.time():
            return True
        return False

    async def update(self) -> None:
        """Fetch the info endpoint and parse the return."""
        if not self.update_required:
            return

        try:
            result = await self._get_info()
        except httpx.TransportError as err:
            raise GatewayCommunicationError(
                "Transport error trying to communicate with gateway",
                request=err.request,
            )
        except httpx.TimeoutException:
            raise EnvoyFirmwareFatalCheckError(500, "Timeout connecting to Envoy")
        except httpx.ConnectError:
            raise EnvoyFirmwareFatalCheckError(500, "Unable to connect to Envoy")
        except httpx.HTTPError:
            raise EnvoyFirmwareCheckError(500, "Unable to query firmware version")
        
        else:
            xml = etree.fromstring(result.content)
            if (device_tag := xml.find("device")) is not None:
                # software version
                if (software_tag := device_tag.find("software")) is not None:
                    self.firmware_version = AwesomeVersion(
                        software_tag.text[1:] # remove leading letter
                    )
                # serial number
                if (sn_tag := device_tag.find("sn")) is not None:
                    self.serial_number = sn_tag.text
                # part number
                if (pn_tag := device_tag.find("pn")) is not None:
                    self.part_number = pn_tag.text
                # imeter
                if (imeter_tag := device_tag.find("imeter")) is not None:
                    self.imeter = imeter_tag.text
                
            if (web_tokens_tag := xml.find("web-tokens")) is not None:
                self.web_tokens = web_tokens_tag.text 
            
            self._last_fetch = time.time()
            self.populated = True

    async def _get_info(self) -> None:
        """Fetch the info endpoint."""
        try:
            return await async_get(
                self._async_client,
                f"https://{self._host}/info",
                retries=1,
            )

        except (httpx.ConnectError, httpx.TimeoutException):
            # Firmware < 7.0.0 does not support HTTPS so we need to try HTTP
            # as a fallback, worse sometimes http will redirect to https://localhost
            # which is not helpful
            return await async_get(
                self._async_client,
                f"http://{self._host}/info",
                retries=1,
            )
            
            
        
        