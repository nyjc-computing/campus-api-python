"""campus_python.audit.v1.root

Root resource for audit v1 API.
"""

from ..interface import ResourceRoot
from .apikeys import ApiKeys
from .journeys import Journeys
from .traces import Traces


class AuditRoot(ResourceRoot):
    """Root resource for audit v1 API.

    Groups all v1 resources under a single entry point.
    """

    url_prefix: str = "audit/v1"

    def __init__(self, json_client=None):
        """Initialize the audit root.

        Args:
            json_client: The HTTP client to use for requests.
        """
        super().__init__(json_client=json_client)

    @property
    def traces(self) -> Traces:
        """Get the traces resource."""
        if not hasattr(self, "_traces"):
            self._traces = Traces(
                client=self._client,
                root=self
            )
        return self._traces

    @property
    def journeys(self) -> Journeys:
        """Get the journeys resource."""
        if not hasattr(self, "_journeys"):
            self._journeys = Journeys(
                client=self._client,
                root=self
            )
        return self._journeys

    @property
    def apikeys(self) -> ApiKeys:
        """Get the apikeys resource."""
        if not hasattr(self, "_apikeys"):
            self._apikeys = ApiKeys(
                client=self._client,
                root=self
            )
        return self._apikeys
