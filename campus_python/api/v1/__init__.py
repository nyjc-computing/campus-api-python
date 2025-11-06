"""campus.python.api

Campus API resource.
"""

from ...interface import ResourceRoot
from ...json_client.interface import JsonClient
from . import (
    circles,
)

class ApiRoot(ResourceRoot):
    """Campus API resource."""
    path = "/api/v1"

    def __init__(self, json_client: JsonClient):
        self._json_client = json_client
        self._clients = None
        self._circles = None

    @property
    def circles(self) -> circles.Circles:
        """Get the circles resource."""
        if not self._circles:
            self._circles = circles.Circles(
                self._json_client,
                root=self
            )
        return self._circles
