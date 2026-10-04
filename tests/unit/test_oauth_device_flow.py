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

    def make_error_response(self, error) -> Mock:
        response = Mock()
        response.status_code = 400
        response.json.return_value = error
        self.client.post.return_value = response
        return response

    def assert_oauth_error(self, oauth_error: str):
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.auth.oauth.poll_for_token(
                client_id="campus-cli", device_code="dev123"
            )
        self.assertEqual(ctx.exception.oauth_error, oauth_error)

    def test_authorization_pending(self):
        self.make_error_response({
            "error": "authorization_pending",
            "error_description": "desc: authorization_pending",
        })
        self.assert_oauth_error("authorization_pending")

    def test_slow_down(self):
        self.make_error_response({
            "error": "slow_down",
            "error_description": "desc: slow_down",
        })
        self.assert_oauth_error("slow_down")

    def test_expired_token(self):
        self.make_error_response({
            "error": "expired_token",
            "error_description": "desc: expired_token",
        })
        self.assert_oauth_error("expired_token")

    def test_access_denied(self):
        self.make_error_response({
            "error": "access_denied",
            "error_description": "desc: access_denied",
        })
        self.assert_oauth_error("access_denied")

    def test_unknown_error(self):
        self.make_error_response({
            "error": "something_else",
            "error_description": "desc: something_else",
        })
        self.assert_oauth_error("something_else")


class TestPollForTokenErrorEnvelopes(unittest.TestCase):
    """The token endpoint emits three error shapes; all must resolve to
    the same oauth_error (#87):

    - Campus envelope (dev/staging): oauth_error lives in details
    - Campus envelope with details stripped (production): recovered
      from the AUTH_* code
    - flat RFC 6749: {"error": <oauth_error>}
    """

    def setUp(self):
        self.auth, self.client = make_auth()

    def poll_error(self, payload: dict) -> errors.AuthenticationError:
        response = Mock()
        response.status_code = 400
        response.json.return_value = payload
        self.client.post.return_value = response
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.auth.oauth.poll_for_token(
                client_id="campus-cli", device_code="dev123"
            )
        return ctx.exception

    def test_campus_envelope_with_details(self):
        err = self.poll_error({
            "error": {
                "code": "AUTH_SLOW_DOWN",
                "message": "Slow down",
                "details": {"oauth_error": "slow_down"},
                "request_id": None,
            }
        })
        self.assertEqual(err.oauth_error, "slow_down")
        self.assertEqual(err.error_description, "Slow down")

    def test_campus_envelope_stripped_details(self):
        """Production strips details; the AUTH_* code identifies the
        OAuth error."""
        err = self.poll_error({
            "error": {
                "code": "AUTH_AUTHORIZATION_PENDING",
                "message": "Authorization pending",
                "request_id": None,
            }
        })
        self.assertEqual(err.oauth_error, "authorization_pending")

    def test_campus_envelope_nonstandard_code_mapping(self):
        """Codes that don't follow AUTH_<OAUTH_ERROR> map explicitly."""
        err = self.poll_error({
            "error": {
                "code": "AUTH_UNSUPPORTED_GRANT",
                "message": "Unsupported grant type",
                "request_id": None,
            }
        })
        self.assertEqual(err.oauth_error, "unsupported_grant_type")


class TestWaitForToken(unittest.TestCase):
    """wait_for_token() implements the RFC 8628 §3.5 polling loop the
    CLI's poll_for_token() owned (issue #87)."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def token_response(self) -> Mock:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"access_token": "tok123"}
        return response

    def error_response(self, payload: dict) -> Mock:
        response = Mock()
        response.status_code = 400
        response.json.return_value = payload
        return response

    def pending(self) -> Mock:
        return self.error_response({
            "error": {
                "code": "AUTH_AUTHORIZATION_PENDING",
                "message": "Authorization pending",
                "request_id": None,
            }
        })

    def with_error(self, oauth_error: str) -> Mock:
        return self.error_response({
            "error": {
                "code": f"AUTH_{oauth_error.upper()}",
                "message": oauth_error,
                "request_id": None,
            }
        })

    def wait(self, max_attempts: int = 5, **kwargs) -> dict:
        return self.auth.oauth.wait_for_token(
            client_id="campus-cli",
            device_code="dev123",
            interval=5,
            max_attempts=max_attempts,
            sleep=self.sleep,
            **kwargs,
        )

    def test_returns_token_after_pending_polls(self):
        self.client.post.side_effect = [
            self.pending(), self.pending(), self.token_response(),
        ]
        result = self.wait()
        self.assertEqual(result, {"access_token": "tok123"})
        self.assertEqual(self.sleeps, [5, 5])

    def test_on_pending_fires_per_pending_poll(self):
        self.client.post.side_effect = [
            self.pending(), self.token_response(),
        ]
        pends: list[int] = []
        self.wait(on_pending=lambda: pends.append(1))
        self.assertEqual(len(pends), 1)

    def test_slow_down_raises_interval_persistently(self):
        """RFC 8628 §3.5: the +5s adjustment persists for the remainder
        of the flow, not just the next attempt."""
        self.client.post.side_effect = [
            self.with_error("slow_down"), self.pending(), self.token_response(),
        ]
        self.wait()
        self.assertEqual(self.sleeps, [10, 10])

    def test_expired_token_is_fatal(self):
        self.client.post.side_effect = [self.with_error("expired_token")]
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.wait()
        self.assertEqual(ctx.exception.oauth_error, "expired_token")
        self.assertEqual(self.sleeps, [])

    def test_access_denied_is_fatal(self):
        self.client.post.side_effect = [self.with_error("access_denied")]
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.wait()
        self.assertEqual(ctx.exception.oauth_error, "access_denied")

    def test_unknown_error_is_fatal(self):
        self.client.post.side_effect = [
            self.with_error("unsupported_grant_type")
        ]
        with self.assertRaises(errors.AuthenticationError):
            self.wait()

    def test_network_error_retries_on_nonfinal_attempt(self):
        self.client.post.side_effect = [
            errors.ServerError(error_description="connection reset"),
            self.token_response(),
        ]
        result = self.wait()
        self.assertEqual(result, {"access_token": "tok123"})
        self.assertEqual(self.sleeps, [5])

    def test_network_error_on_final_attempt_propagates(self):
        self.client.post.side_effect = [
            errors.ServerError(error_description="connection reset")
        ] * 3
        with self.assertRaises(errors.ServerError):
            self.wait(max_attempts=3)
        # Two retries after the first failure, no third
        self.assertEqual(self.client.post.call_count, 3)
        self.assertEqual(self.sleeps, [5, 5])

    def test_timeout_raises_authentication_error(self):
        self.client.post.side_effect = [self.pending()] * 5
        with self.assertRaises(errors.AuthenticationError) as ctx:
            self.wait(max_attempts=5)
        self.assertIsNone(ctx.exception.oauth_error)
        self.assertIn("timed out", ctx.exception.error_description)

    def test_default_interval_when_server_omits_it(self):
        self.client.post.side_effect = [self.pending(), self.token_response()]
        self.auth.oauth.wait_for_token(
            client_id="campus-cli",
            device_code="dev123",
            interval=None,
            max_attempts=5,
            sleep=self.sleep,
        )
        self.assertEqual(self.sleeps, [5])


if __name__ == "__main__":
    unittest.main()
