"""Unit tests for the audit API-key role catalogue.

Verifies role resolution semantics: catalogue listing, role → scopes,
and the scopes/role mutual-exulsion rules (#918).

Ported concern from the flask-campus dist's campus.audit.roles
(flask-campus#31); the suite's service-side tests (tests/unit/audit/
test_key_roles.py in campus weekly) cover the mint-route integration.

File: tests/unit/test_audit_roles.py
"""

import unittest

from campus_python.audit import roles


class TestRoleCatalogue(unittest.TestCase):
    """resolve_role and list_roles behave per the catalogue."""

    def test_list_roles_returns_copies(self):
        listed = roles.list_roles()
        self.assertEqual(listed, roles.CATALOGUE)
        listed["traces-viewer"].append("apikeys:write")
        self.assertNotIn(
            "apikeys:write", roles.list_roles()["traces-viewer"],
            "list_roles() must return copies, not the live catalogue",
        )

    def test_resolve_role_known(self):
        self.assertEqual(
            roles.resolve_role("traces-viewer"), ["traces:read"]
        )
        self.assertEqual(
            roles.resolve_role("traces-producer"),
            ["traces:read", "traces:search", "traces:write"],
        )

    def test_resolve_role_unknown_raises(self):
        with self.assertRaises(roles.UnknownRoleError):
            roles.resolve_role("superadmin")

    def test_no_role_resolves_to_wildcard(self):
        for scopes in roles.list_roles().values():
            self.assertNotIn("*", scopes)


class TestResolveScopes(unittest.TestCase):
    """resolve_scopes merges the role/scope input rules."""

    def test_role_only(self):
        self.assertEqual(
            roles.resolve_scopes(role="key-operator"),
            ["apikeys:read", "apikeys:write"],
        )

    def test_scope_list(self):
        self.assertEqual(
            roles.resolve_scopes(["traces:read", "traces:write"]),
            ["traces:read", "traces:write"],
        )

    def test_scope_csv_string(self):
        self.assertEqual(
            roles.resolve_scopes("traces:read, traces:write"),
            ["traces:read", "traces:write"],
        )

    def test_role_and_scopes_rejected(self):
        with self.assertRaises(ValueError):
            roles.resolve_scopes(["traces:read"], role="traces-viewer")

    def test_empty_returns_empty(self):
        self.assertEqual(roles.resolve_scopes(), [])


if __name__ == "__main__":
    unittest.main()
