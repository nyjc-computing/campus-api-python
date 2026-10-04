"""Contract tests for the auth connections resource (issue #71).

Routes mirror campus/auth/routes/connections.py (campus weekly): the
auth app sets strict_slashes, so DELETE needs the trailing slash on
/connections/<provider>/ and /connections/<provider>/<integration>/.
user_id travels as a query parameter for delegated (basic auth) calls
and is ignored by the server under a bearer token.
"""

import unittest
from unittest.mock import Mock

from campus_python.auth.v1 import AuthRoot


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


CONNECTION = {
    "provider": "google.classroom",
    "integration": "classroom",
    "scopes": ["https://www.googleapis.com/auth/classroom.rosters"],
    "connected_at": "2026-10-04T00:00:00+00:00",
    "expires_at": None,
}


class TestConnectionsList(unittest.TestCase):
    """connections.list() must GET the collection, optionally delegated."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.get.return_value.json.return_value = {
            "connections": [CONNECTION]
        }

    def test_list_gets_connections_collection(self):
        connections = self.auth.connections.list()
        self.client.get.assert_called_once_with(
            "/auth/v1/connections/", query=None
        )
        self.assertEqual(connections, [CONNECTION])

    def test_list_sends_delegated_user_id_query(self):
        self.auth.connections.list(user_id="user-1")
        self.client.get.assert_called_once_with(
            "/auth/v1/connections/", query={"user_id": "user-1"}
        )


class TestConnectionsDelete(unittest.TestCase):
    """Disconnect routes must carry trailing slashes and optional user_id."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def test_provider_delete_uses_trailing_slash(self):
        self.auth.connections["google"].delete()
        self.client.delete.assert_called_once_with(
            "/auth/v1/connections/google/", query=None
        )

    def test_provider_delete_sends_delegated_user_id(self):
        self.auth.connections["google"].delete(user_id="user-1")
        self.client.delete.assert_called_once_with(
            "/auth/v1/connections/google/", query={"user_id": "user-1"}
        )

    def test_integration_delete_targets_namespaced_route(self):
        self.auth.connections["google"]["classroom"].delete()
        self.client.delete.assert_called_once_with(
            "/auth/v1/connections/google/classroom/", query=None
        )

    def test_integration_delete_sends_delegated_user_id(self):
        self.auth.connections["google"]["classroom"].delete(user_id="user-1")
        self.client.delete.assert_called_once_with(
            "/auth/v1/connections/google/classroom/",
            query={"user_id": "user-1"},
        )


if __name__ == "__main__":
    unittest.main()
