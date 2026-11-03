"""Unit tests for the injectable session-id provider (sessionstore).

Hosts that own their own request state (flask_campus) install a
provider that resolves the current auth-session/login-session ids per
lane, keeping the SDK framework-free. Resolution order everywhere:
explicit argument > provider > the legacy flask.session read.
"""

import unittest
from unittest.mock import Mock, patch

import flask

from campus_python.auth.v1 import AuthRoot, set_session_id_provider
from campus_python.auth.v1 import sessionstore
from campus_python.auth.v1.logins import LOGIN_STORAGE_KEY
from campus_python.auth.v1.sessions import CampusSessions, SESSION_STORAGE_KEY

LOGIN_TOKEN_PAYLOAD = {
    "access_token": "tok-live",
    "token_type": "Bearer",
    "expires_in": 432000,
    "scope": "campus.profile",
    "user_id": "user1",
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    client.authorization = None  # property read in token()
    return AuthRoot(json_client=client), client


def ok_response(body: dict) -> Mock:
    response = Mock()
    response.json.return_value = body
    return response


def session_context():
    """A Flask request context with a writable session."""
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    return app.test_request_context()


class TestStorageKeyConstants(unittest.TestCase):
    """The storage-key constants pin the legacy flask.session keys."""

    def setUp(self):
        self.auth, _ = make_auth()

    def test_session_storage_key_matches_derivation(self):
        self.assertEqual(
            SESSION_STORAGE_KEY, self.auth.sessions._session_key
        )

    def test_login_storage_key_matches_derivation(self):
        self.assertEqual(LOGIN_STORAGE_KEY, self.auth.logins._session_key)


class TestSessionIdProvider(unittest.TestCase):
    """Provider resolution: explicit argument > provider > legacy read."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def tearDown(self):
        set_session_id_provider(None)

    def test_provider_consulted_outside_any_request_context(self):
        """The provider answers even where flask.session cannot."""
        set_session_id_provider(
            lambda kind: "login-123"
            if kind == sessionstore.LANE_LOGIN
            else None
        )
        self.assertTrue(self.auth.logins.has_session())
        # Login.path carries a trailing slash; .session_id (which
        # splits on "/") is therefore empty — assert on the path.
        self.assertTrue(
            self.auth.logins[None].path.endswith("logins/login-123/")
        )

    def test_without_provider_outside_request_context_raises(self):
        """No provider: the legacy flask.session lane is preserved."""
        with self.assertRaises(RuntimeError):
            self.auth.logins.has_session()

    def test_explicit_id_wins_over_provider(self):
        set_session_id_provider(
            lambda kind: "login-123"
            if kind == sessionstore.LANE_LOGIN
            else None
        )
        self.assertTrue(
            self.auth.logins["login-999"].path.endswith("logins/login-999/")
        )

    def test_provider_lanes_are_isolated(self):
        """A provider answering only the session lane leaves logins to
        the legacy lane."""
        set_session_id_provider(
            lambda kind: "sess-abc"
            if kind == sessionstore.LANE_SESSION
            else None
        )
        self.assertTrue(self.auth.sessions.has_session())
        with session_context():
            self.assertFalse(self.auth.logins.has_session())

    def test_token_uses_provider_resolved_id(self):
        """logins.token() targets the provider's session id."""
        set_session_id_provider(
            lambda kind: "login-123"
            if kind == sessionstore.LANE_LOGIN
            else None
        )
        self.client.post.return_value = ok_response(LOGIN_TOKEN_PAYLOAD)
        token = self.auth.logins.token()
        self.assertEqual(token.access_token, "tok-live")
        path = self.client.post.call_args[0][0]
        self.assertIn("logins/login-123/token", path)

    def test_sessions_from_session_explicit_id(self):
        """An explicit id bypasses provider and flask.session entirely."""
        with patch.object(
                CampusSessions.Session, "get", autospec=True
        ) as mock_get:
            self.auth.sessions.from_session(session_id="sess-99")
        instance = mock_get.call_args[0][0]
        self.assertIn("sess-99", instance.path)
