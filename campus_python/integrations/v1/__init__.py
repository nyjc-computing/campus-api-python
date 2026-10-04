"""campus.python.integrations.v1

Campus integrations registry resource (v1).

Read-only service catalog of the first-party integrations Campus
offers, served by the auth service at /integrations/v1 (#688,
#56). The endpoint is public — everything it returns is already
observable by starting a connect flow — so the resource works in
both server and device modes without extra authorization.
"""

import campus.model

from ...interface import ResourceRoot


class IntegrationsRoot(ResourceRoot):
    """Campus integrations registry resource (auth service, v1).

    Usage:
        client.integrations.list()  # -> list[campus.model.Integration]
    """

    # Trailing slash matches the Flask route (GET /integrations/v1/);
    # make_path() preserves it verbatim.
    url_prefix: str = "/integrations/v1/"

    def list(self) -> "list[campus.model.Integration]":
        """List the first-party integrations Campus offers.

        Returns:
            list[campus.model.Integration]: Registry entries with
            public catalog metadata only (no secrets). If
            enable/disable flags are added server-side later, they
            surface behind this same resource.
        """
        resp = self.client.get(self.make_path())
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return [
            campus.model.Integration.from_resource(item)
            for item in resp.json().get("integrations", [])
        ]
