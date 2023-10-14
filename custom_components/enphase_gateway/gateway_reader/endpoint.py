"""GatewayEndpoint class."""

import time


class GatewayEndpoint:
    """Class representing a Gateway endpoint."""

    def __init__(
            self,
            endpoint_path: str,
            cache: int = 0,
            fetch: bool = True
    ) -> None:
        """Initialize instance of GatewayEndpoint."""
        self.path = endpoint_path
        self.cache = cache
        self.fetch = fetch
        self._last_fetch = None
        self._base_url = "{}://{}/{}"

    def __repr__(self):
        """Magic method. Use path for representation."""
        return self.path

    @property
    def update_required(self) -> bool:
        """Check if an update is required for this endpoint."""
        if self.fetch is False:
            return False
        elif not self._last_fetch:
            return True
        elif (self._last_fetch + self.cache) <= time.time():
            return True

        return False

    def get_url(self, protocol, host):
        """Return formatted url."""
        return self._base_url.format(protocol, host, self.path)

    def success(self, timestamp: float = None):
        """Update the last_fetch timestamp."""
        if not timestamp:
            timestamp = time.time()
        self._last_fetch = timestamp
