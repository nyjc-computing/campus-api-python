"""campus.python.auth.v1.root

Campus Auth root resource (v1).

Resource for root actions, only meant for Campus (non-auth) backend
deployments.
"""

from typing import Any

from campus.common import schema
import campus.model

from ...interface import ResourceCollection
from ... import errors


class Root(ResourceCollection):
    """Campus Auth root resource."""
    path = "root"

    def authenticate(
            self,
            *,
            token: str | None = None,
            client_id: schema.CampusID | None = None,
            client_secret: str | None = None,
    ) -> dict[str, Any]:
        """Authenticate the given token or client credentials.
        
        Returns: {
            "client": { ... }
        } or {
            "client": { ... },
            "user": { ... }
        }
        """
        if token:
            resp = self.client.post(self.make_url(), json={"token": token})
        elif client_id and client_secret:
            resp = self.client.post(
                self.make_url(),
                json={"client_id": client_id, "client_secret": client_secret}
            )
        else:
            raise errors.AuthenticationError(
                error_description="Missing or incomplete authentication information."
            )
        resp.raise_for_status()
        body = resp.json()
        body["client"] = campus.model.Client.from_resource(body["client"])
        if "user" in body:
            body["user"] = campus.model.User.from_resource(body["user"])
        return body
