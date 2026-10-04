"""campus.python.auth.v1.broker

Campus Auth token broker resource (v1).

The sanctioned release path for upstream provider access tokens:
Campus stays sole custodian of upstream credentials, and this endpoint
hands the short-lived access token (never the refresh token) to
confidential clients flagged `token_bridge`, on behalf of the bearer's
user. Errors arrive as APIError subclasses through raise_for_status —
e.g. 403 carries details.missing_scopes, 401 maps to
AuthenticationError — so consumers can branch on them without
hand-mapping statuses.
"""

from ...interface import JsonDict, ResourceRoot


class Broker(ResourceRoot):
    """Campus Auth token broker resource."""
    url_prefix = "/auth/v1/broker"

    def __init__(self, root: ResourceRoot):
        super().__init__(json_client=root.client)
        self._root = root

    def token(
            self,
            provider: str,
            integration: "str | None" = None,
            *,
            min_scopes: "list[str] | None" = None,
    ) -> JsonDict:
        """Release the bearer's upstream access token for a provider.

        Args:
            provider: Base provider (e.g. "google")
            integration: Integration slug for the namespaced route
                (e.g. "classroom" → /broker/google/classroom/)
            min_scopes: Scopes the caller requires; denied unless the
                user's upstream grant covers them and the client's
                upstream_scopes allowlist permits them

        Returns:
            {provider, user_id, access_token, token_type, expires_in,
            scope} — the refresh token never leaves Campus

        Raises:
            errors.NotFoundError: No connection for this provider
                (404); namespaced providers pointed at the identity
                route are redirected to the integration route the
                same way
            errors.AuthenticationError: Bearer session expired (401)
            errors.APIError: 403 with details.missing_scopes, or 400
                AUTH_INVALID_SCOPE / configuration problems
        """
        if integration:
            path = self.make_path(f"{provider}/{integration}/")
        else:
            path = self.make_path(f"{provider}/")
        json_body: JsonDict = {}
        if min_scopes is not None:
            json_body["min_scopes"] = min_scopes
        resp = self.client.post(path, json=json_body)
        resp.raise_for_status()
        return resp.json()
