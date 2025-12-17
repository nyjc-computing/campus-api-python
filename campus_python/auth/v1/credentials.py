"""campus.python.auth.v1.credentials

Campus Auth credentials resource (v1).

This mirrors the style used in `clients.py` and provides a
`Credentials` collection which can be indexed by provider, then by
user id to operate on credentials resources.
"""

from campus.common import env
import campus.model

from ...interface import JsonDict, Resource, ResourceCollection


class Credentials(ResourceCollection):
    """Campus Auth Credentials resource.

    Usage:
    - `creds = Credentials(root=...)`
    - `creds["github"].get(token_id)` -> get by token id
    - `creds["github"][user_id].get(client_id)` -> get credentials for user
    """
    path = "credentials/"

    def __getitem__(self, provider: str) -> "Credentials.Provider":
        """Get provider-level collection."""
        return Credentials.Provider(provider, parent=self)

    class Provider(Resource):
        """Provider-level credentials resource.

        Instance `path` is set to include the provider name so that
        requests are made to /{base}/{credentials}/{provider}.
        """

        def __getitem__(self, user_id: str) -> "Credentials.Provider.User":
            """Get a user-specific credential resource."""
            return Credentials.Provider.User(user_id, parent=self)

        def get(self, token_id: str) -> campus.model.UserCredentials:
            resp = self.client.get(
                self.make_path(),
                query={"token_id": token_id}
            )
            resp.raise_for_status()
            return campus.model.UserCredentials.from_resource(resp.json())

        def list(self) -> list[campus.model.UserCredentials]:
            resp = self.client.get(self.make_path())
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return [
                campus.model.UserCredentials.from_resource(item)
                for item in resp.json().get("credentials", [])
            ]

        class User(Resource):
            """Credentials for a single user under a provider."""

            def delete(self) -> None:
                client_id = env.CLIENT_ID
                resp = self.client.delete(
                    self.make_path(),
                    json={"client_id": client_id}
                )
                # Raise error if status code is not 2XX or 3XX
                resp.raise_for_status()

            def get(self) -> campus.model.UserCredentials:
                client_id = env.CLIENT_ID
                resp = self.client.get(
                    self.make_path(),
                    query={"client_id": client_id}
                )
                # Raise error if status code is not 2XX or 3XX
                resp.raise_for_status()
                return campus.model.UserCredentials.from_resource(resp.json())

            def new(
                    self,
                    scopes: list[str],
                    expiry_seconds: int,
            ) -> campus.model.UserCredentials:
                raise NotImplementedError(
                    "Method not expected to be called on API"
                )

            def update(self, token: campus.model.OAuthToken) -> None:
                client_id = env.CLIENT_ID
                json_data: JsonDict = {
                    "client_id": client_id,
                    "token": token.to_resource()
                }
                resp = self.client.patch(self.make_path(), json=json_data)
                # Raise error if status code is not 2XX or 3XX
                resp.raise_for_status()
