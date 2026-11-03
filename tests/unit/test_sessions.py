"""Unit tests for the auth sessions resource.

The SDK holds no request state of its own: Session.finalize() returns
the server's (target, user) payload and leaves client-side storage to
the host. The public storage-key constants pin the keys flask_campus
writes session ids into.
"""

import unittest
from unittest.mock import Mock

from campus_python.auth.v1 import AuthRoot
from campus_python.auth.v1.logins import LOGIN_STORAGE_KEY
from campus_python.auth.v1.sessions import SESSION_STORAGE_KEY


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


def ok_response(body: dict) -> Mock:
    response = Mock()
    response.json.return_value = body
    return response


class TestStorageKeys(unittest.TestCase):
    """The public storage-key constants pin the keys flask_campus
    writes its session/login ids into."""

    def test_session_storage_key(self):
        self.assertEqual(SESSION_STORAGE_KEY, "campus_session_id")

    def test_login_storage_key(self):
        self.assertEqual(LOGIN_STORAGE_KEY, "logins_login_id")


class TestSessionFinalize(unittest.TestCase):
    """finalize() returns the server's target + embedded user (#879)."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.delete.return_value = ok_response(
            {"target": "https://app.example.org/after-login"}
        )

    def test_finalize_parses_embedded_user(self):
        """The #879 embed rides along as a User model."""
        self.client.delete.return_value = ok_response({
            "target": "https://app.example.org/after-login",
            "user": {
                "id": "user-1",
                "created_at": "2026-10-05T00:00:00+00:00",
                "email": "user@example.org",
                "name": "Test User",
            },
        })
        target, user = self.auth.sessions["sess-1"].finalize()
        self.assertEqual(target, "https://app.example.org/after-login")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.id, "user-1")
        self.assertEqual(user.email, "user@example.org")


class TestLoginRevoke(unittest.TestCase):
    """Login.revoke() must tolerate an absent Flask session key."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.delete.return_value = ok_response({})

if __name__ == "__main__":
    unittest.main()
