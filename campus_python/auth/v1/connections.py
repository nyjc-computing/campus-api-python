"""campus.python.auth.v1.connections

Campus Auth connections resource (v1).

The user-facing view of the upstream credentials Campus custodies:
which providers/integrations a user has granted, and an explicit way
to revoke that grant. Metadata only — token values never appear here
(release stays broker-only); disconnecting the campus provider is
logout and is rejected by the server (revoke via oauth.revoke instead).
"""

from ...interface import JsonDict, Resource, ResourceCollection


class Connections(ResourceCollection):
    """Campus Auth Connections resource."""
    path = "connections/"

    def __getitem__(self, provider: str) -> "Connections.Connection":
        """Get a specific provider's connection resource."""
        return Connections.Connection(provider, parent=self)

    def list(
            self,
            *,
            user_id: "str | None" = None,
    ) -> "list[JsonDict]":
        """List the target user's upstream connections.

        Each entry carries {provider, integration, scopes, connected_at,
        expires_at} — never token values. Auth shape mirrors the server:
        a bearer token acts for its own user (user_id ignored), while
        basic (client-credentials) auth must name a user via user_id.

        Args:
            user_id: Delegated target user (required for basic auth)

        Returns:
            List of connection metadata dicts
        """
        query = {"user_id": user_id} if user_id else None
        resp = self.client.get(self.make_path(), query=query)
        resp.raise_for_status()
        return resp.json()["connections"]

    class Connection(Resource):
        """Single provider connection resource."""

        def __getitem__(
                self,
                integration: str,
        ) -> "Connections.Connection.Integration":
            """Get an integration-namespaced connection resource."""
            return Connections.Connection.Integration(
                integration, parent=self
            )

        def delete(self, *, user_id: "str | None" = None) -> None:
            """Disconnect every credential for this base provider.

            404 (NotFoundError) means there was nothing to disconnect;
            callers treating disconnect as idempotent can catch it.

            Args:
                user_id: Delegated target user (required for basic auth)
            """
            query = {"user_id": user_id} if user_id else None
            resp = self.client.delete(
                self.make_path(end_slash=True),
                query=query,
            )
            resp.raise_for_status()
            return None

        class Integration(Resource):
            """Integration-namespaced connection resource."""

            def delete(self, *, user_id: "str | None" = None) -> None:
                """Disconnect this provider integration (e.g. google/classroom).

                Args:
                    user_id: Delegated target user (required for basic auth)
                """
                query = {"user_id": user_id} if user_id else None
                resp = self.client.delete(
                    self.make_path(end_slash=True),
                    query=query,
                )
                resp.raise_for_status()
                return None
