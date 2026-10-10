"""Unit tests for the embedded session user (#879).

The auth service embeds the session user in session reads,
finalization, and login-session reads for the session-owning client;
the SDK prefers the embed and falls back to the operator-gated users
route on older services or model versions (campus#879, companion to
the campus-side embedding change).
"""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import campus.model
import flask

from campus_python.auth.v1 import AuthRoot

SESSION_ID = "auth-session-1"

USER_RESOURCE = {
    "id": "user-1",
    "created_at": "2026-10-01T00:00:00+00:00",
    "email": "student@nyjc.edu.sg",
    "name": "Test Student",
}

EMBEDDED_USER = campus.model.User.from_resource(USER_RESOURCE)

TOKEN_RESOURCE = {
    "id": "token-1",
    "created_at": "2026-10-05T00:00:00+00:00",
    "expires_at": "2026-10-12T00:00:00+00:00",
    "expires_in": 604800,
    "token_type": "Bearer",
    "refresh_token": "refresh-1",
    "scope": "campus.profile",
    "user_id": "user-1",
}

AUTH_SESSION_RESOURCE = {
    "id": SESSION_ID,
    "created_at": "2026-10-01T00:00:00+00:00",
    "expires_at": "2026-11-01T00:00:00+00:00",
    "provider": "campus",
    "client_id": "client-1",
    "user_id": "user-1",
    "redirect_uri": "https://app.example.org/finalize_login",
    "scopes": [],
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


def session_context():
    """A Flask request context with a writable session."""
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    return app.test_request_context()


class TestFinalizeUsesEmbed(unittest.TestCase):
    """finalize() answers step 4 from the embed when present."""

    def setUp(self):
        self.auth, _ = make_auth()

    def run_finalize(self, finalize_return: tuple) -> None:
        sessions = MagicMock()
        sessions.from_code.return_value = SimpleNamespace(
            id=SESSION_ID,
            user_id="user-1",
            redirect_uri="https://app.example.org/finalize_login",
            device_id=None,
        )
        sessions[SESSION_ID].finalize.return_value = finalize_return
        self.auth._sessions = sessions
        users = MagicMock()
        users["user-1"].get.return_value = EMBEDDED_USER
        self.auth._users = users
        logins = MagicMock()
        self.auth._logins = logins
        token_response = Mock()
        token_response.json.return_value = TOKEN_RESOURCE
        self.auth.client.post.return_value = token_response

        app = flask.Flask(__name__)
        app.secret_key = "test-secret"
        with patch.dict(os.environ, {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec"}), \
                app.test_request_context(
                    "/finalize_login", headers={"User-Agent": "pytest"}):
            self.auth.finalize(
                state=SESSION_ID, code="code-1", scope="campus.profile"
            )

    def test_embedded_user_skips_users_route(self):
        """The embed answers the user-exists check without users.get."""
        self.run_finalize(("https://app.example.org/landing", EMBEDDED_USER))
        self.assertFalse(self.auth._users["user-1"].get.called)

    def test_no_embed_falls_back_to_users_route(self):
        """Pre-#879 services return no embed; users.get stays the check."""
        self.run_finalize(("https://app.example.org/landing", None))
        self.assertTrue(self.auth._users["user-1"].get.called)


class TestPushContextUsesEmbed(unittest.TestCase):
    """push_context() hydrates g.user from the embed when present."""

    def setUp(self):
        self.auth, _ = make_auth()

    def push_session(self, session_obj) -> object:
        sessions = MagicMock()
        sessions._session_key = "campus_session_id"
        sessions.has_session.return_value = True
        sessions.from_session.return_value = session_obj
        self.auth._sessions = sessions
        users = MagicMock()
        users["user-1"].get.return_value = EMBEDDED_USER
        self.auth._users = users
        with session_context():
            flask.session["campus_session_id"] = SESSION_ID
            self.auth.push_context()
            return flask.g.user

    def push_login(self, login_obj) -> object:
        logins = MagicMock()
        logins._session_key = "logins_login_id"
        logins.has_session.return_value = True
        logins.from_session.return_value = login_obj
        self.auth._logins = logins
        users = MagicMock()
        users["user-1"].get.return_value = EMBEDDED_USER
        self.auth._users = users
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            self.auth.push_context()
            return flask.g.user

    def test_session_embed_skips_users_route(self):
        session = SimpleNamespace(user_id="user-1", user=EMBEDDED_USER)
        user = self.push_session(session)
        self.assertEqual(user.email, USER_RESOURCE["email"])
        self.assertFalse(self.auth._users["user-1"].get.called)

    def test_session_without_embed_falls_back(self):
        session = SimpleNamespace(user_id="user-1", user=None)
        user = self.push_session(session)
        self.assertEqual(user.email, USER_RESOURCE["email"])
        self.assertTrue(self.auth._users["user-1"].get.called)

    def test_model_without_user_field_falls_back(self):
        """An installed campus-suite predating the field still resolves."""
        session = campus.model.AuthSession.from_resource(
            AUTH_SESSION_RESOURCE
        )
        assert not hasattr(session, "user"), (
            "campus-suite now carries the field; this skew case needs a "
            "pre-#879 fixture instead"
        )
        user = self.push_session(session)
        self.assertEqual(user.email, USER_RESOURCE["email"])
        self.assertTrue(self.auth._users["user-1"].get.called)

    def test_login_embed_skips_users_route(self):
        login = SimpleNamespace(
            user_id="user-1", user=EMBEDDED_USER, device_id="device-1"
        )
        user = self.push_login(login)
        self.assertEqual(user.email, USER_RESOURCE["email"])
        self.assertFalse(self.auth._users["user-1"].get.called)

    def test_login_without_embed_falls_back(self):
        login = SimpleNamespace(user_id="user-1", user=None, device_id=None)
        user = self.push_login(login)
        self.assertEqual(user.email, USER_RESOURCE["email"])
        self.assertTrue(self.auth._users["user-1"].get.called)


if __name__ == "__main__":
    unittest.main()
