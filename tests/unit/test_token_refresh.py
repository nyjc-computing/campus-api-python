"""Unit tests for the session-token path.

Campus._get_token_from_session() re-acquires the session user's campus
bearer with ONE call to POST /auth/v1/logins/{session_id}/token
(campus#963/#964, invariant A10) — the operator-gated credentials
GET → refresh grant → credentials PATCH legs (#854) are gone, with no
fallback to them. The server rotates an expired grant token itself, so
the client sends no body and never writes back.

Also covers the public-client refresh helper auth.refresh(stored)
(client issue #87): it presents the stored refresh token with the
issuing client_id and returns the rotated pair.
"""

import json
import os
import unittest
from unittest.mock import Mock, patch

import campus.model
import flask
import requests

from campus_python import Campus, errors
from campus_python.auth.v1 import AuthRoot
from campus_python.json_client import CampusResponse

RFC_REFRESH_PAYLOAD = {
    "access_token": "tok-new",
    "token_type": "Bearer",
    "expires_in": 86400,
    "refresh_token": "rt-new",
    "scope": "campus.profile",
}

LOGIN_TOKEN_PAYLOAD = {
    "access_token": "tok-live",
    "token_type": "Bearer",
    "expires_in": 432000,
    "scope": "campus.profile",
    "user_id": "user1",
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client.

    headers.get defaults to None (no ambient Authorization header) —
    token() restores whatever header it finds, so tests that exercise
    the ambient-bearer path override this.
    """
    client = Mock()
    client.headers.get.return_value = None
    return AuthRoot(json_client=client), client


def make_campus() -> tuple[Campus, Mock]:
    """Create a Campus whose auth root is backed by a mock client."""
    client = Mock()
    campus = Campus.__new__(Campus)
    campus._mode = "server"
    campus.timeout = 5
    campus._auth = AuthRoot(json_client=client)
    return campus, client


def make_response(status_code: int, payload: dict) -> CampusResponse:
    """Build a CampusResponse over a real requests.Response so
    raise_for_status() runs the actual error-envelope mapping."""
    raw = requests.Response()
    raw.status_code = status_code
    raw._content = json.dumps(payload).encode("utf-8")
    raw.headers["Content-Type"] = "application/json"
    return CampusResponse(raw)


def session_context():
    """A Flask request context with a writable session."""
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    return app.test_request_context()


class TestGetTokenFromSession(unittest.TestCase):
    """The session bearer comes from the login-session token route."""

    def test_delegates_to_logins_token_once(self):
        campus, client = make_campus()
        auth = campus.auth

        logins = Mock()
        live = Mock(access_token="tok-live")
        logins.token.return_value = live
        auth._logins = logins

        result = campus._get_token_from_session()

        self.assertIs(result, live)
        logins.token.assert_called_once_with()
        # One endpoint call, nothing else: no credentials GET, no
        # refresh grant, no PATCH write-back (#854 lanes are gone).
        client.get.assert_not_called()
        client.post.assert_not_called()
        client.patch.assert_not_called()


class TestLoginSessionTokenRoute(unittest.TestCase):
    """logins.token() POSTs /auth/v1/logins/{id}/token (#117)."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.post.return_value = make_response(
            200, dict(LOGIN_TOKEN_PAYLOAD)
        )

    def test_posts_to_session_token_route(self):
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            token = self.auth.logins.token()

        self.assertEqual(token.access_token, "tok-live")
        self.assertEqual(token.scope, "campus.profile")
        # The user_id echo survives as provider metadata (#648)
        self.assertEqual(token.provider_fields.get("user_id"), "user1")
        args, kwargs = self.client.post.call_args
        # Canonical route has no trailing slash; the session id and
        # the client's Basic credentials carry the request — no body.
        self.assertEqual(args[0], "/auth/v1/logins/login-1/token")
        self.assertIsNone(kwargs.get("json"))

    def test_get_token_uses_the_same_route(self):
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            token = self.auth.get_token()

        self.assertEqual(token.access_token, "tok-live")
        self.client.get.assert_not_called()
        self.client.patch.assert_not_called()

    def test_no_login_session_raises_without_http(self):
        with session_context():
            with self.assertRaises(errors.AuthenticationError):
                self.auth.logins.token()
        self.client.post.assert_not_called()

    def test_invalid_grant_surfaces_oauth_error(self):
        """A gone session or campus grant is invalid_grant — the
        caller's cue to require re-login (#87 convention)."""
        self.client.post.return_value = make_response(400, {
            "error": {
                "code": "AUTH_INVALID_GRANT",
                "message": "Invalid or expired login session",
                "details": {"oauth_error": "invalid_grant"},
                "request_id": None,
            }
        })
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            with self.assertRaises(errors.APIError) as ctx:
                self.auth.logins.token()
        self.assertEqual(ctx.exception.oauth_error, "invalid_grant")


class TestLoginTokenPresentsBasicOnly(unittest.TestCase):
    """The session-token route serves client principals only (#963/A10):
    token() must present Basic credentials even when an ambient bearer
    is set — a with_user_session() nested inside another one otherwise
    presents the outer session's user token and is refused with 403.
    The prior header is restored afterwards."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.post.return_value = make_response(
            200, dict(LOGIN_TOKEN_PAYLOAD)
        )

    def _call(self):
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            return self.auth.logins.token()

    def test_forces_basic_when_bearer_is_set(self):
        self.client.headers.get.return_value = "Bearer outer-user-token"
        self._call()
        calls = [name for name, _, _ in self.client.mock_calls
                 if name in ("reset_authorization", "post",
                             "set_bearer_authorization")]
        # The exact ordering contract: drop the ambient bearer (Basic),
        # make the call, then restore it.
        self.assertEqual(
            ["reset_authorization", "post", "set_bearer_authorization"], calls
        )

    def test_restores_ambient_bearer_after_the_call(self):
        self.client.headers.get.return_value = "Bearer outer-user-token"
        self._call()
        self.client.set_bearer_authorization.assert_called_once_with(
            "outer-user-token"
        )

    def test_failure_still_restores_ambient_bearer(self):
        self.client.headers.get.return_value = "Bearer outer-user-token"
        self.client.post.return_value = make_response(403, {
            "error": {"code": "FORBIDDEN", "message": "denied"}
        })
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            with self.assertRaises(errors.APIError):
                self.auth.logins.token()
        self.client.set_bearer_authorization.assert_called_once_with(
            "outer-user-token"
        )

    def test_no_ambient_header_leaves_basic_in_place(self):
        self.client.headers.get.return_value = None
        self._call()
        self.client.reset_authorization.assert_called_once()
        self.client.set_bearer_authorization.assert_not_called()


class TestPublicClientRefresh(unittest.TestCase):
    """auth.refresh(stored) presents the stored refresh token with the
    issuing client_id and returns the rotated pair (#87)."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.post.return_value = make_response(
            200, dict(RFC_REFRESH_PAYLOAD)
        )
        self.stored = campus.model.OAuthToken(
            id="tok-old",
            expires_in=3600,
            refresh_token="rt-old",
            scopes=["campus.profile"],
        )

    def test_returns_rotated_pair(self):
        refreshed = self.auth.refresh(self.stored, client_id="campus-cli")

        self.assertEqual(refreshed.access_token, "tok-new")
        self.assertEqual(refreshed.refresh_token, "rt-new")
        # The stored token is unchanged; rotation is the caller's to persist
        self.assertEqual(self.stored.refresh_token, "rt-old")

    def test_sends_stored_refresh_token_with_client_id(self):
        self.auth.refresh(self.stored, client_id="campus-cli")

        args, kwargs = self.client.post.call_args
        self.assertEqual(args[0], "/auth/v1/oauth/token")
        self.assertEqual(kwargs["json"]["grant_type"], "refresh_token")
        self.assertEqual(kwargs["json"]["client_id"], "campus-cli")
        self.assertEqual(kwargs["json"]["refresh_token"], "rt-old")

    def test_client_id_falls_back_to_env(self):
        with patch.dict(os.environ, {"CLIENT_ID": "cid123"}):
            self.auth.refresh(self.stored)

        kwargs = self.client.post.call_args.kwargs
        self.assertEqual(kwargs["json"]["client_id"], "cid123")

    def test_stored_token_without_refresh_token_is_rejected(self):
        bare = campus.model.OAuthToken(id="tok-bare", expires_in=3600)
        with self.assertRaises(errors.AuthenticationError):
            self.auth.refresh(bare, client_id="campus-cli")
        self.client.post.assert_not_called()

    def test_invalid_grant_maps_to_apierror_with_oauth_error(self):
        """A rejected refresh token raises with the OAuth error code in
        details — the caller's cue to fall back to re-login."""
        self.client.post.return_value = make_response(400, {
            "error": {
                "code": "AUTH_INVALID_GRANT",
                "message": "Invalid or expired refresh token",
                "details": {"oauth_error": "invalid_grant"},
                "request_id": None,
            }
        })
        with self.assertRaises(errors.APIError) as ctx:
            self.auth.refresh(self.stored, client_id="campus-cli")
        self.assertEqual(ctx.exception.oauth_error, "invalid_grant")

    def test_invalid_grant_stripped_details_still_identifies_error(self):
        """Production strips error details; the AUTH_* code still
        identifies the OAuth error (#87)."""
        self.client.post.return_value = make_response(400, {
            "error": {
                "code": "AUTH_INVALID_GRANT",
                "message": "Invalid or expired refresh token",
                "request_id": None,
            }
        })
        with self.assertRaises(errors.APIError) as ctx:
            self.auth.refresh(self.stored, client_id="campus-cli")
        self.assertEqual(ctx.exception.oauth_error, "invalid_grant")


if __name__ == "__main__":
    unittest.main()
