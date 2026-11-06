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
    path = "credentials"

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

        def get(
                self,
                token_id: str,
                include_token: bool = False,
        ) -> campus.model.UserCredentials:
            """Get one credential record.

            Reads are redacted by default (campus#1055): the joined
            token carries metadata only. include_token=True opts into
            the raw token — an operator-principal power on the
            service, honored on per-record reads only.
            """
            query: JsonDict = {"token_id": token_id}
            if include_token:
                query["include"] = "token"
            return campus.model.UserCredentials.from_resource(
                self._get_json(self.make_path(end_slash=True), query=query)
            )

        def list(self) -> "list[campus.model.UserCredentials]":
            """List credential records (admin view, campus#1055).

            Records carry token metadata only: the service never
            releases raw tokens in bulk, include opt-ins are honored
            on per-record reads exclusively.
            """
            body = self._get_json(self.make_path(end_slash=True))
            return [
                campus.model.UserCredentials.from_resource(item)
                for item in body.get("credentials", [])
            ]

        class User(Resource):
            """Credentials for a single user under a provider."""

            def delete(self, client_id: str | None = None) -> None:
                """Disconnect this user's credential record.

                Deletes the calling client's record by default;
                campus#1055 opens the body client_id to the operator
                so a deployment admin can disconnect an arbitrary
                integration's stored record for (provider, user).
                """
                target = client_id or env.CLIENT_ID
                self._delete_json(
                    self.make_path(end_slash=True),
                    json={"client_id": target}
                )

            def get(self, include_token: bool = False) -> campus.model.UserCredentials:
                """Get this user's credential record (redacted by
                default; include_token opts into the raw token,
                campus#1055)."""
                client_id = env.CLIENT_ID
                query: JsonDict = {"client_id": client_id}
                if include_token:
                    query["include"] = "token"
                return campus.model.UserCredentials.from_resource(
                    self._get_json(self.make_path(end_slash=True), query=query)
                )

            def new(
                    self,
                    scopes: "list[str]",
                    expires_in: int,
            ) -> campus.model.UserCredentials:
                """Issue new credentials for this provider and user.

                POST /credentials/<provider>/<user_id> with body
                {scopes, expires_in}; the client_id comes from the
                request's auth context, not the body.

                Returns:
                    The created UserCredentials
                """
                return campus.model.UserCredentials.from_resource(
                    self._post_json(
                        self.make_path(end_slash=True),
                        json={"scopes": scopes, "expires_in": expires_in}
                    )
                )

            def update(self, token: campus.model.OAuthToken) -> None:
                """Replace this user's stored token for the provider.

                The client_id rides on the body from the environment;
                the token is sent as its full resource form.

                Args:
                    token: The new OAuthToken to store.
                """
                client_id = env.CLIENT_ID
                json_data: JsonDict = {
                    "client_id": client_id,
                    "token": token.to_resource()
                }
                self._patch_json(self.make_path(end_slash=True), json=json_data)
