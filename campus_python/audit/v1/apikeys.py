"""campus.python.audit.v1.apikeys

Campus Audit API keys resource (v1).

API keys are the audit service's own auth material (audit_v1_...),
managed here: create, list, inspect, update, revoke, regenerate.
Plaintext key values are returned exactly once, at creation and at
regeneration.
"""

from ...interface import JsonDict, Resource, ResourceCollection


class APIKeys(ResourceCollection):
    """Campus Audit API keys resource."""
    path = "apikeys/"

    def __getitem__(self, api_key_id: str) -> "APIKeys.APIKey":
        """Get a specific API key resource by ID."""
        return APIKeys.APIKey(api_key_id, parent=self)

    def new(
            self,
            *,
            name: str,
            owner_id: str,
            scopes: "list[str]",
            rate_limit: "int | None" = None,
            expires_at: "str | None" = None,
    ) -> JsonDict:
        """Create an API key.

        Args:
            name: Key name
            owner_id: Owner user ID
            scopes: Scope strings the key grants (e.g. ["traces:read"])
            rate_limit: Requests per minute (optional)
            expires_at: ISO 8601 expiry (optional)

        Returns:
            The created key record; its plaintext `api_key` value is
            shown only here.
        """
        payload: JsonDict = {
            "name": name,
            "owner_id": owner_id,
            "scopes": scopes,
        }
        if rate_limit is not None:
            payload["rate_limit"] = rate_limit
        if expires_at is not None:
            payload["expires_at"] = expires_at
        resp = self.client.post(self.make_path(), json=payload)
        resp.raise_for_status()
        return resp.json()

    def list(
            self,
            *,
            owner_id: "str | None" = None,
            active_only: bool = True,
            limit: "int | None" = None,
    ) -> JsonDict:
        """List API keys with optional filtering.

        Args:
            owner_id: Filter by owner user ID
            active_only: Only non-expired, non-revoked keys (default True)
            limit: Page size (server default 50)

        Returns:
            {"api_keys": [...], "count": int}
        """
        query: JsonDict = {}
        if owner_id is not None:
            query["owner_id"] = owner_id
        # The server parses bool query values from the lowercase
        # literals true/false (flask_campus _BOOL_LITERALS); Python's
        # str(True) capitalization would 422.
        query["active_only"] = str(active_only).lower()
        if limit is not None:
            query["limit"] = limit
        resp = self.client.get(self.make_path(), query=query)
        resp.raise_for_status()
        return resp.json()

    class APIKey(Resource):
        """Single campus audit API key resource."""

        def get(self) -> JsonDict:
            """Get this API key's record (no key hash or plaintext)."""
            resp = self.client.get(self.make_path(end_slash=True))
            resp.raise_for_status()
            return resp.json()

        def update(
                self,
                *,
                name: "str | None" = None,
                scopes: "list[str] | None" = None,
                rate_limit: "int | None" = None,
        ) -> JsonDict:
            """Update this API key's mutable fields.

            Only name, scopes, and rate_limit are mutable; use
            revoke() to disable the key. The server rejects an empty
            update, so at least one field must be provided.

            Returns:
                The updated key record
            """
            payload: JsonDict = {}
            if name is not None:
                payload["name"] = name
            if scopes is not None:
                payload["scopes"] = scopes
            if rate_limit is not None:
                payload["rate_limit"] = rate_limit
            if not payload:
                raise ValueError(
                    "At least one field must be provided for update"
                )
            resp = self.client.patch(
                self.make_path(end_slash=True), json=payload
            )
            resp.raise_for_status()
            return resp.json()

        def revoke(self) -> None:
            """Revoke this API key (the record is kept for audit)."""
            resp = self.client.delete(self.make_path(end_slash=True))
            resp.raise_for_status()
            return None

        def regenerate(self) -> str:
            """Regenerate this API key's value.

            The old value stops working immediately.

            Returns:
                The new plaintext key value, shown only here.
            """
            resp = self.client.post(
                self.make_path("regenerate", end_slash=False)
            )
            resp.raise_for_status()
            return resp.json()["key"]
