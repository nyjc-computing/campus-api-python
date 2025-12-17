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

    class Vault(Resource):
        """A single vault (label) exposing mapping-like access."""

        def keys(self) -> list[str]:
            resp = self.client.get(self.make_path())
            resp.raise_for_status()
            body = resp.json()
            return body["keys"]

        def __delitem__(self, key: str) -> None:
            resp = self.client.delete(self.make_path(key))
            if resp.status_code == 404:
                raise KeyError(key)
            resp.raise_for_status()
            return None

        def __getitem__(self, key: str) -> str:
            resp = self.client.get(self.make_path(key))
            # translate 404 into KeyError for route compatibility
            if resp.status_code == 404:
                raise KeyError(key)
            resp.raise_for_status()
            body = resp.json()
            # expected shape: {"key": value}
            return body["key"]

        def __setitem__(self, key: str, value: Any) -> None:
            resp = self.client.post(self.make_path(key), json={"value": value})
            resp.raise_for_status()
            return None
