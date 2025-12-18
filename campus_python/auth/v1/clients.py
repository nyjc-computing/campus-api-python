"""campus.python.auth.v1.clients

Campus Auth Clients resource (v1).
"""

from campus.common import env
import campus.model

from ...interface import JsonDict, Resource, ResourceCollection


class Clients(ResourceCollection):
    """Campus Auth Clients resource."""
    path = "clients/"

    def __getitem__(self, client_id: str) -> "Clients.Client":
        """Get a specific client resource by ID."""
        return Clients.Client(client_id, parent=self)

    def list(self) -> list[campus.model.Client]:
        resp = self.client.get(self.make_path())
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return [
            campus.model.Client.from_resource(item)
            for item in resp.json()["clients"]
        ]

    def new(self, name: str, description: str) -> campus.model.Client:
        resp = self.client.post(self.make_path(), json={
            "name": name,
            "description": description,
        })
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return campus.model.Client.from_resource(resp.json())

    class Client(Resource):
        """Campus Auth Client resource."""

        @property
        def access(self) -> "Clients.Client.ClientAccess":
            return Clients.Client.ClientAccess("access", parent=self)

        @property
        def client_id(self) -> str:
            """The client_id of the resource was passed in as a path
            parameter, and is extracted using this property alias.
            """
            return self.path.strip("/")

        def delete(self) -> None:
            resp = self.client.delete(self.make_path())
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()

        def get(self) -> campus.model.Client:
            resp = self.client.get(self.make_path())
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.Client.from_resource(resp.json())

        def revoke(self) -> None:
            resp = self.client.post(self.make_path("revoke"))
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()

        def update(self, name: str | None = None, description: str | None = None) -> campus.model.Client:
            json_data = {}
            if name is not None:
                json_data["name"] = name
            if description is not None:
                json_data["description"] = description
            resp = self.client.put(self.make_path(), json=json_data)
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.Client.from_resource(resp.json())

        class ClientAccess(Resource):
            """Campus Auth Client Access resource."""

            def get(
                    self,
                    vault: str | None = None
            ) -> JsonDict:
                if vault:
                    resp = self.client.get(
                        self.make_path(),
                        query={"vault": vault}
                    )
                else:
                    resp = self.client.get(self.make_path())
                # Raise error if status code is not 2XX or 3XX
                resp.raise_for_status()
                return resp.json()

            def grant(
                    self,
                    vault: str,
                    permission: int,
            ) -> JsonDict:
                resp = self.client.post(self.make_path("grant"), json={
                    "vault": vault,
                    "permission": permission,
                })
                # Raise error if status code is not 2XX or 3XX
                resp.raise_for_status()
                return resp.json()

            def revoke(
                    self,
                    vault: str,
                    permission: int,
            ) -> JsonDict:
                resp = self.client.post(self.make_path("revoke"), json={
                    "vault": vault,
                    "permission": permission,
                })
                # Raise error if status code is not 2XX or 3XX
                resp.raise_for_status()
                return resp.json()
