"""Contract tests for the auth token broker resource (issue #72).

Routes mirror campus/auth/routes/broker.py (campus weekly): POST
/auth/v1/broker/<provider>/ (identity) and
/auth/v1/broker/<provider>/<integration>/ (namespaced), body
{"min_scopes": [...]} or {}. The response is a flat dict carrying the
upstream access token; errors surface as APIError subclasses via
raise_for_status (campus-classroom currently raw-requests this
endpoint and hand-maps the statuses).
"""

import unittest
from unittest.mock import Mock

from campus_python.auth.v1 import AuthRoot


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


BROKER_TOKEN = {
    "provider": "google",
    "user_id": "user-1",
    "access_token": "ya29.upstream",
    "token_type": "Bearer",
    "expires_in": 1234,
    "scope": "email profile",
}


class TestBrokerToken(unittest.TestCase):
    """broker.token() must POST the identity/integration broker routes."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.post.return_value.json.return_value = BROKER_TOKEN

    def test_identity_route_posts_empty_body(self):
        token = self.auth.broker.token("google")
        self.client.post.assert_called_once_with(
            "/auth/v1/broker/google/", json={}
        )
        self.assertEqual(token, BROKER_TOKEN)

    def test_min_scopes_passed_through(self):
        self.auth.broker.token(
            "google",
            min_scopes=["https://www.googleapis.com/auth/calendar"],
        )
        self.assertEqual(
            self.client.post.call_args.kwargs["json"],
            {"min_scopes": ["https://www.googleapis.com/auth/calendar"]},
        )

    def test_integration_route_targets_namespaced_path(self):
        self.auth.broker.token("google", "classroom")
        self.client.post.assert_called_once_with(
            "/auth/v1/broker/google/classroom/", json={}
        )

    def test_integration_route_with_min_scopes(self):
        self.auth.broker.token(
            "google",
            "classroom",
            min_scopes=["https://www.googleapis.com/auth/classroom.rosters"],
        )
        self.assertEqual(
            self.client.post.call_args.kwargs["json"],
            {
                "min_scopes": [
                    "https://www.googleapis.com/auth/classroom.rosters"
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
