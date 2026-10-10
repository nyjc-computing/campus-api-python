"""Unit tests for the auth sessions resource (issue #59).

Session.finalize() and Login.revoke() must not raise KeyError when the
Flask session key is absent (expired cookie, new worker, lost session) —
the remote operation has already succeeded by the time local session
state is cleared. The provider-qualified Flask session key must also be
"campus_session_id" (the trailing-slash path used to yield the empty
provider, storing state under "_session_id").
"""

import unittest
from unittest.mock import Mock

import flask

from campus_python.auth.v1 import AuthRoot


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


def session_context():
    """A Flask request context with a writable session."""
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    return app.test_request_context()


def ok_response(body: dict) -> Mock:
    response = Mock()
    response.json.return_value = body
    return response


class TestSessionKey(unittest.TestCase):
    """The Flask session key is provider-qualified."""

    def setUp(self):
        self.auth, _ = make_auth()

    def test_session_key_names_the_provider(self):
        sessions = self.auth.sessions
        self.assertEqual(sessions._session_key, "campus_session_id")


class TestSessionFinalize(unittest.TestCase):
    """finalize() must tolerate an absent Flask session key (#59)."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.delete.return_value = ok_response(
            {"target": "https://app.example.org/after-login"}
        )

    def test_finalize_removes_session_key(self):
        with session_context():
            flask.session["campus_session_id"] = "sess-1"
            target, user = self.auth.sessions["sess-1"].finalize()
            self.assertEqual(target, "https://app.example.org/after-login")
            self.assertIsNone(user)
            self.assertNotIn("campus_session_id", flask.session)

    def test_finalize_succeeds_without_session_key(self):
        with session_context():
            target, _ = self.auth.sessions["sess-1"].finalize()
            self.assertEqual(target, "https://app.example.org/after-login")

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
        with session_context():
            target, user = self.auth.sessions["sess-1"].finalize()
            self.assertEqual(target, "https://app.example.org/after-login")
            self.assertIsNotNone(user)
            self.assertEqual(user.id, "user-1")
            self.assertEqual(user.email, "user@example.org")


class TestLoginRevoke(unittest.TestCase):
    """Login.revoke() must tolerate an absent Flask session key."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.delete.return_value = ok_response({})

    def test_revoke_removes_session_key(self):
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            self.auth.logins["login-1"].revoke()
            self.assertNotIn("logins_login_id", flask.session)

    def test_revoke_succeeds_without_session_key(self):
        with session_context():
            self.auth.logins["login-1"].revoke()


if __name__ == "__main__":
    unittest.main()
