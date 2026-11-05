"""campus.python.auth.v1.vaults

Campus Auth vaults resource (v1).

Provides a `Vaults` collection where each vault (by label) behaves like a
mapping of key -> value. Supports keys(), item access, assignment and
deletion. 404 responses for missing keys are translated to KeyError to match
the server route expectations.
"""

from typing import Any

from ...interface import Resource, ResourceCollection


class Vaults(ResourceCollection):
    """Campus Auth Vaults resource."""
    path = "vaults/"

    def __getitem__(self, label: str) -> "Vaults.Vault":
        return Vaults.Vault(label, parent=self)

    def labels(self) -> "list[str]":
        """List vault labels (admin view, campus#1055).

        GET /vaults/ — the operator, the super-admin root, or
        designated users holding any vault grant row plus the
        vaults:read scope; client principals hold per-label access
        only and cannot enumerate.
        """
        return self._get_json(self.make_path()).get("labels", [])

    class Vault(Resource):
        """A single vault (label) exposing mapping-like access."""

        def keys(self) -> "list[str]":
            body = self._get_json(self.make_path(end_slash=True))
            return body["keys"]

        def __delitem__(self, key: str) -> None:
            resp = self.client.delete(self.make_path(key, end_slash=True))
            if resp.status_code == 404:
                raise KeyError(key)
            resp.raise_for_status()
            return None

        def __getitem__(self, key: str) -> str:
            resp = self.client.get(self.make_path(key, end_slash=True))
            # translate 404 into KeyError for route compatibility
            if resp.status_code == 404:
                raise KeyError(key)
            resp.raise_for_status()
            body = resp.json()
            # expected shape: {"key": value}
            return body["key"]

        def __setitem__(self, key: str, value: Any) -> None:
            self._post_json(self.make_path(key, end_slash=True), json={"value": value})
            return None
