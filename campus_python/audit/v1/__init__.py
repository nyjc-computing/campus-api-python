"""campus.python.audit.v1

Campus Audit service resource root (/audit/v1).

The audit service authenticates with a dedicated audit API key
(`audit_v1_...`) sent as a Bearer token — not CLIENT_ID/CLIENT_SECRET
— so its resource root gets its own JsonClient rather than sharing the
auth/api one.
"""

from ...interface import ResourceRoot
from ...json_client.interface import JsonClient
from . import apikeys, traces


class AuditRoot(ResourceRoot):
    """Campus Audit service resource."""
    url_prefix = "/audit/v1"

    def __init__(self, json_client: JsonClient):
        super().__init__(json_client=json_client)
        self._apikeys = None
        self._traces = None

    @property
    def apikeys(self) -> apikeys.APIKeys:
        """Get the API keys resource."""
        if not self._apikeys:
            self._apikeys = apikeys.APIKeys(root=self)
        return self._apikeys

    @property
    def traces(self) -> traces.Traces:
        """Get the traces resource."""
        if not self._traces:
            self._traces = traces.Traces(root=self)
        return self._traces
