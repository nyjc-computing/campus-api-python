"""Contract tests for the auth users resource (campus-cli#42).

The campus auth server gates user management behind the users:*
management scopes and implements PATCH /users/{id} as rename-only
(a user's id IS its email), so Users.User.update() must send PATCH
with exactly {"name": ...} and no other field.
"""

import unittest
from unittest.mock import Mock

import campus.model

from campus_python.auth.v1 import AuthRoot

# User resource shape emitted by campus weekly
# (campus/auth/routes/users.py responses).
USER_RESOURCE = {
    "id": "user@example.com",
    "created_at": "2026-09-30T06:31:24.582763+00:00",
    "email": "user@example.com",
    "name": "Test User",
    "activated_at": None,
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


class TestUsersUpdatePatchVerb(unittest.TestCase):
    """Users.User.update() must send PATCH carrying only the name."""

    def setUp(self):
        self.auth, self.client = make_auth()
        response = Mock()
        response.json.return_value = USER_RESOURCE
        self.client.patch.return_value = response

    def test_update_sends_patch_with_name(self):
        user = self.auth.users["user@example.com"].update(name="New Name")
        self.client.patch.assert_called_once()
        self.client.put.assert_not_called()
        args, kwargs = self.client.patch.call_args
        self.assertEqual(args[0], "/auth/v1/users/user@example.com/")
        self.assertEqual(kwargs["json"], {"name": "New Name"})
        self.assertIsInstance(user, campus.model.User)
        self.assertEqual(user.id, "user@example.com")
        self.assertEqual(user.name, "Test User")

    def test_update_returns_updated_user(self):
        response = Mock()
        response.json.return_value = {**USER_RESOURCE, "name": "Renamed"}
        self.client.patch.return_value = response
        user = self.auth.users["user@example.com"].update(name="Renamed")
        self.assertEqual(user.name, "Renamed")


if __name__ == "__main__":
    unittest.main()
