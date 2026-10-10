"""campus.python.auth.v1.grants

Campus Auth grants resource (v1).

The access-grant store (#883): resource-keyed rows granting a user or
client principal management authority over a vocabulary (level grants
compared via the monotonic scope algebra) or bitflag access to a vault
label. Administration routes in campus/auth/routes/grants.py; GET
/grants/ is the "who can administer what" matrix query.

Grant rows are plain dicts (the server's AccessGrant resource): id,
grantee_type, grantee_id, resource_type, resource_id, bits, level,
created_at. Vault rows carry bits (1=READ, 2=CREATE, 4=UPDATE,
8=DELETE); management rows carry level (read < mod < write < admin).
"""

from ...interface import JsonDict, ResourceCollection


class Grants(ResourceCollection):
    """Campus Auth access-grant store."""
    path = "grants/"

    def list(
            self,
            *,
            grantee_type: "str | None" = None,
            grantee_id: "str | None" = None,
            resource_type: "str | None" = None,
            resource_id: "str | None" = None,
    ) -> JsonDict:
        """List access-grant rows.

        Authorization: unfiltered lists require the operator; user
        principals may list only the single vocabulary they
        administer.

        Args:
            grantee_type: Filter by "user" or "client"
            grantee_id: Filter by grantee identity (user email / client id)
            resource_type: Filter by vocabulary ("users", "clients",
                "vault", ...)
            resource_id: Filter by instance (vault label)

        Returns:
            {"grants": [...]}
        """
        query: JsonDict = {}
        if grantee_type is not None:
            query["grantee_type"] = grantee_type
        if grantee_id is not None:
            query["grantee_id"] = grantee_id
        if resource_type is not None:
            query["resource_type"] = resource_type
        if resource_id is not None:
            query["resource_id"] = resource_id
        resp = self.client.get(self.make_path(), query=query or None)
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return resp.json()

    def check(
            self,
            *,
            grantee_type: str,
            grantee_id: str,
            resource_type: str,
            resource_id: str = "",
            bits: "int | None" = None,
            level: "str | None" = None,
    ) -> bool:
        """Check whether a grantee's row covers a permission.

        Authorization: operator, or a same-vocabulary admin.

        Args:
            grantee_type: "user" or "client"
            grantee_id: Grantee identity
            resource_type: Vocabulary ("users", "clients", "vault", ...)
            resource_id: Instance (vault label; default none)
            bits: Vault bitflag mask to test
            level: Management level to test

        Returns:
            True when the held row covers the requested permission
        """
        query: JsonDict = {
            "grantee_type": grantee_type,
            "grantee_id": grantee_id,
            "resource_type": resource_type,
        }
        if resource_id:
            query["resource_id"] = resource_id
        if bits is not None:
            query["bits"] = bits
        if level is not None:
            query["level"] = level
        resp = self.client.get(self.make_path("check", end_slash=False), query=query)
        resp.raise_for_status()
        return bool(resp.json().get("granted"))

    def grant(
            self,
            *,
            grantee_type: str,
            grantee_id: str,
            resource_type: str,
            resource_id: str = "",
            bits: "int | None" = None,
            level: "str | None" = None,
    ) -> JsonDict:
        """Grant access (create a row, or raise an existing one).

        Authorization: operator, or a same-vocabulary admin. Vault
        bits OR into the existing mask; management levels never
        downgrade — revoke first to lower a level.

        Anti-escalation (#883): no principal may administer its own
        grants, and vocabulary-level clients:admin rows are rejected
        (operator-equivalent).

        Args:
            grantee_type: "user" or "client"
            grantee_id: Grantee identity
            resource_type: Vocabulary ("users", "clients", "vault", ...)
            resource_id: Instance (required for vault labels)
            bits: Vault bitflag mask (vaults only)
            level: Management level (read/mod/write/admin)

        Returns:
            The grant row (post-application state)
        """
        body: JsonDict = {
            "grantee_type": grantee_type,
            "grantee_id": grantee_id,
            "resource_type": resource_type,
        }
        if resource_id:
            body["resource_id"] = resource_id
        if bits is not None:
            body["bits"] = bits
        if level is not None:
            body["level"] = level
        resp = self.client.post(self.make_path(), json=body)
        resp.raise_for_status()
        return resp.json()["grant"]

    def revoke(
            self,
            *,
            grantee_type: str,
            grantee_id: str,
            resource_type: str,
            resource_id: str = "",
            bits: "int | None" = None,
            level: "str | None" = None,
    ) -> "JsonDict | None":
        """Revoke access (clear vault bits, delete covered levels).

        Authorization: operator, or a same-vocabulary admin. Vault
        rows delete at zero bits; a revoked level's row is deleted
        when the held level covers it.

        Args:
            grantee_type: "user" or "client"
            grantee_id: Grantee identity
            resource_type: Vocabulary
            resource_id: Instance (vault label)
            bits: Vault bitflag mask to clear
            level: Management level to revoke

        Returns:
            The remaining grant row, or None when the row was deleted
        """
        body: JsonDict = {
            "grantee_type": grantee_type,
            "grantee_id": grantee_id,
            "resource_type": resource_type,
        }
        if resource_id:
            body["resource_id"] = resource_id
        if bits is not None:
            body["bits"] = bits
        if level is not None:
            body["level"] = level
        resp = self.client.post(self.make_path("revoke", end_slash=False), json=body)
        resp.raise_for_status()
        return resp.json()["grant"]

    def delete(self, grant_id: str) -> None:
        """Delete a grant row outright by its id.

        Authorization: operator, or a same-vocabulary admin for the
        row's vocabulary.

        Args:
            grant_id: The grant row's id (from list())
        """
        resp = self.client.delete(self.make_path(grant_id, end_slash=False))
        resp.raise_for_status()
