"""Unit tests for the OAuth device-flow resource (RFC 8628).

All OAuth endpoints live under /auth/v1/oauth on the auth service
(campus/auth/routes/oauth.py, branch ``weekly``) and the auth app sets
``strict_slashes``, so the client must POST the exact /auth/v1/oauth/...
paths — absolute /oauth/... paths 404 against real deployments.

OAuth error responses must raise AuthenticationError carrying the OAuth
error code in ``details`` (readable via ``APIError.oauth_error``), not a
TypeError from an unsupported ``error_code=`` kwarg.
"""

import unittest
from unittest.mock import Mock

from campus_python import errors
from campus_python.auth.v1 import AuthRoot


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


class TestDeviceFlowPaths(unittest.TestCase):
    """Device-flow requests must target the /auth/v1/oauth endpoints."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def test_request_device_code_posts_device_authorize_endpoint(self):
        self.auth.oauth.request_device_code(client_id="campus-cli")
        self.client.post.assert_called_once_with(
            "/auth/v1/oauth/device_authorize",
            json={"client_id": "campus-cli"},
        )

    def test_poll_for_token_posts_token_endpoint(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"access_token": "tok123"}
        self.client.post.return_value = response
        self.auth.oauth.poll_for_token(
            client_id="campus-cli", device_code="dev123"
        )
        self.client.post.assert_called_once_with(
            "/auth/v1/oauth/token",
            json={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": "campus-cli",
                "device_code": "dev123",
            },
        )

    def test_authorize_device_posts_device_authorize_endpoint(self):
        self.auth.oauth.authorize_device(user_code="ABCD-1234", user_id="user1")
        self.client.post.assert_called_once_with(
            "/auth/v1/oauth/device/authorize",
            json={"user_code": "ABCD-1234", "user_id": "user1"},
        )


class TestPollForTokenErrors(unittest.TestCase):
    """RFC 8628 error responses map to AuthenticationError, not TypeError."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def make_error_response(self, error: str) -> Mock:
        response = Mock()
        response.status_code = 400
        response.json.return_value = {
            "error": error,
            "error_description": f"desc: {error}",
        }
        self.client.post.return_value = response
        return response

    def test_authorization_pending(self):
        self.make_error_response("authorization_pending")
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.auth.oauth.poll_for_token(
                client_id="campus-cli", device_code="dev123"
            )
        self.assertEqual(ctx.exception.oauth_error, "authorization_pending")

    def test_slow_down(self):
        self.make_error_response("slow_down")
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.auth.oauth.poll_for_token(
                client_id="campus-cli", device_code="dev123"
            )
        self.assertEqual(ctx.exception.oauth_error, "slow_down")

    def test_expired_token(self):
        self.make_error_response("expired_token")
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.auth.oauth.poll_for_token(
                client_id="campus-cli", device_code="dev123"
            )
        self.assertEqual(ctx.exception.oauth_error, "expired_token")

    def test_access_denied(self):
        self.make_error_response("access_denied")
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.auth.oauth.poll_for_token(
                client_id="campus-cli", device_code="dev123"
            )
        self.assertEqual(ctx.exception.oauth_error, "access_denied")

    def test_unknown_error(self):
        self.make_error_response("something_else")
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.auth.oauth.poll_for_token(
                client_id="campus-cli", device_code="dev123"
            )
        self.assertEqual(ctx.exception.oauth_error, "something_else")


if __name__ == "__main__":
    unittest.main()
