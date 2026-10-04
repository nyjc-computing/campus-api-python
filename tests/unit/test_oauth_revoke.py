"""Contract tests for OAuth token revocation (RFC 7009, issue #73).

The device flow moved in-library with the PR #70 fix sweep, but
campus-cli still raw-calls POST /auth/v1/oauth/revoke. The endpoint is
registered as the leaf path /oauth/revoke (campus/auth/routes/
oauth.py; the auth app sets strict_slashes) and returns 200 {} per
RFC 7009 section 2.2 regardless of token state.
"""

import unittest
from unittest.mock import Mock

from campus_python.auth.v1 import AuthRoot


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


class TestOAuthRevoke(unittest.TestCase):
    """auth.oauth.revoke() must POST the /oauth/revoke leaf route."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def test_revoke_posts_token_and_client_id(self):
        self.auth.oauth.revoke(token="tok-1", client_id="campus-cli")
        self.client.post.assert_called_once_with(
            "/auth/v1/oauth/revoke",
            json={"token": "tok-1", "client_id": "campus-cli"},
        )

    def test_revoke_sends_token_type_hint_when_given(self):
        self.auth.oauth.revoke(
            token="tok-1",
            client_id="campus-cli",
            token_type_hint="refresh_token",
        )
        self.assertEqual(
            self.client.post.call_args.kwargs["json"],
            {
                "token": "tok-1",
                "client_id": "campus-cli",
                "token_type_hint": "refresh_token",
            },
        )


if __name__ == "__main__":
    unittest.main()
