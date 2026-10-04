"""Unit test for Campus._get_token_from_session token rotation.

After exchanging the refresh token, the refreshed token must be the one
returned — the credentials resource still holds the pre-refresh access
token, and refresh-token grants rotate (single-use) on the server.

Also covers the public-client refresh helper auth.refresh(stored)
(client issue #87): it presents the stored refresh token with the
issuing client_id and returns the rotated pair.
"""

import json
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

import campus.model
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


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


def make_response(status_code: int, payload: dict) -> CampusResponse:
    """Build a CampusResponse over a real requests.Response so
    raise_for_status() runs the actual error-envelope mapping."""
    raw = requests.Response()
    raw.status_code = status_code
    raw._content = json.dumps(payload).encode("utf-8")
    raw.headers["Content-Type"] = "application/json"
    return CampusResponse(raw)


class TestGetTokenFromSession(unittest.TestCase):
    """The refreshed token, not the stale credentials token, is returned."""

    def test_returns_refreshed_token_after_refresh(self):
        with patch.dict(os.environ, {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec"}):
            campus = Campus(timeout=5)
            auth = campus.auth

            old_token = Mock()
            old_token.is_expired.return_value = True
            new_token = Mock()

            auth._logins = Mock()
            auth._logins.from_session.return_value = Mock(user_id="user1")

            creds_resource = Mock()
            creds_resource.get.return_value = Mock(token=old_token)
            provider = MagicMock()
            provider.__getitem__.return_value = creds_resource
            creds_collection = MagicMock()
            creds_collection.__getitem__.return_value = provider
            auth._credentials = creds_collection

            with patch.object(
                    type(auth), "token", return_value=new_token
            ) as token_mock:
                result = campus._get_token_from_session(force_refresh=True)

            self.assertIs(result, new_token)
            token_mock.assert_called_once_with(
                grant_type="refresh_token",
                refresh_token=old_token.refresh_token,
            )
            creds_resource.update.assert_called_once_with(token=new_token)


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
