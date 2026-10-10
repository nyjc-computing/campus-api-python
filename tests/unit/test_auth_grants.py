"""Contract tests for the auth grants resource (campus-cli#50).

The grants surface (#883/#886) is the access-grant store's
administration API: list (the "who can administer what" matrix),
check, grant, revoke, and delete-by-id. The SDK is a thin pass-through
— filters become query params, grant/revoke bodies carry exactly the
caller's fields, and rows are plain dicts (no campus model exists for
AccessGrant).
"""

import unittest
from unittest.mock import Mock

from campus_python.auth.v1 import AuthRoot

# Grant row shape emitted by campus weekly
# (campus/auth/routes/grants.py responses).
GRANT_ROW = {
    "id": "uid-grant-10131fe6",
    "grantee_type": "user",
    "grantee_id": "user@example.com",
    "resource_type": "users",
    "resource_id": "",
    "bits": None,
    "level": "write",
    "created_at": "2026-10-10T15:10:00+00:00",
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


class TestGrantsList(unittest.TestCase):
    """Grants.list() passes filters as query params."""

    def setUp(self):
        self.auth, self.client = make_auth()
        response = Mock()
        response.json.return_value = {"grants": [GRANT_ROW]}
        self.client.get.return_value = response

    def test_list_unfiltered_returns_envelope(self):
        result = self.auth.grants.list()
        args, kwargs = self.client.get.call_args
        self.assertEqual(args[0], "/auth/v1/grants/")
        self.assertIsNone(kwargs["query"])
        self.assertEqual(result["grants"], [GRANT_ROW])

    def test_list_forwards_filters(self):
        self.auth.grants.list(
            grantee_type="user",
            grantee_id="user@example.com",
            resource_type="users",
        )
        kwargs = self.client.get.call_args.kwargs
        self.assertEqual(
            kwargs["query"],
            {
                "grantee_type": "user",
                "grantee_id": "user@example.com",
                "resource_type": "users",
            },
        )


class TestGrantsCheck(unittest.TestCase):
    """Grants.check() returns the granted boolean."""

    def setUp(self):
        self.auth, self.client = make_auth()
        response = Mock()
        response.json.return_value = {"granted": True}
        self.client.get.return_value = response

    def test_check_sends_query_and_returns_bool(self):
        granted = self.auth.grants.check(
            grantee_type="user",
            grantee_id="user@example.com",
            resource_type="users",
            level="write",
        )
        args, kwargs = self.client.get.call_args
        self.assertEqual(args[0], "/auth/v1/grants/check")
        self.assertEqual(
            kwargs["query"],
            {
                "grantee_type": "user",
                "grantee_id": "user@example.com",
                "resource_type": "users",
                "level": "write",
            },
        )
        self.assertIs(granted, True)


class TestGrantsGrantRevoke(unittest.TestCase):
    """grant()/revoke() send exactly the caller's fields."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def test_grant_sends_level_row(self):
        response = Mock()
        response.json.return_value = {"grant": GRANT_ROW}
        self.client.post.return_value = response
        row = self.auth.grants.grant(
            grantee_type="user",
            grantee_id="user@example.com",
            resource_type="users",
            level="write",
        )
        args, kwargs = self.client.post.call_args
        self.assertEqual(args[0], "/auth/v1/grants/")
        self.assertEqual(
            kwargs["json"],
            {
                "grantee_type": "user",
                "grantee_id": "user@example.com",
                "resource_type": "users",
                "level": "write",
            },
        )
        self.assertEqual(row["id"], GRANT_ROW["id"])

    def test_grant_vault_sends_bits_and_label(self):
        response = Mock()
        response.json.return_value = {"grant": {**GRANT_ROW, "level": None, "bits": 1}}
        self.client.post.return_value = response
        self.auth.grants.grant(
            grantee_type="client",
            grantee_id="uid-client-abc",
            resource_type="vault",
            resource_id="email",
            bits=1,
        )
        kwargs = self.client.post.call_args.kwargs
        self.assertEqual(
            kwargs["json"],
            {
                "grantee_type": "client",
                "grantee_id": "uid-client-abc",
                "resource_type": "vault",
                "resource_id": "email",
                "bits": 1,
            },
        )

    def test_revoke_posts_to_revoke_path(self):
        response = Mock()
        response.json.return_value = {"grant": None}
        self.client.post.return_value = response
        row = self.auth.grants.revoke(
            grantee_type="user",
            grantee_id="user@example.com",
            resource_type="users",
            level="write",
        )
        args, _ = self.client.post.call_args
        self.assertEqual(args[0], "/auth/v1/grants/revoke")
        self.assertIsNone(row)

    def test_delete_by_id(self):
        response = Mock()
        self.client.delete.return_value = response
        self.auth.grants.delete("uid-grant-10131fe6")
        args, _ = self.client.delete.call_args
        self.assertEqual(args[0], "/auth/v1/grants/uid-grant-10131fe6")


if __name__ == "__main__":
    unittest.main()
