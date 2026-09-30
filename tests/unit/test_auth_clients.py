"""Contract tests for the auth clients resource (client issue #50).

The campus auth server registers client updates as PATCH-only
(campus/auth/routes/clients.py) and has no PUT routes at all, so
Clients.Client.update() must send PATCH — it previously sent PUT and
every client update failed with 405 Method Not Allowed.
"""

import unittest
from unittest.mock import Mock

import campus.model

from campus_python.auth.v1 import AuthRoot

# Client resource shape emitted by campus weekly
# (campus/auth/routes/clients.py responses).
CLIENT_RESOURCE = {
    "id": "cid123",
    "created_at": "2026-09-30T06:31:24.582763+00:00",
    "name": "campus-cli",
    "description": "CLI client",
    "is_public": True,
    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


class TestClientsUpdatePatchVerb(unittest.TestCase):
    """Clients.Client.update() must send PATCH to the client endpoint."""

    def setUp(self):
        self.auth, self.client = make_auth()
        response = Mock()
        response.json.return_value = CLIENT_RESOURCE
        self.client.patch.return_value = response

    def test_update_sends_patch(self):
        client = self.auth.clients["cid123"].update(
            redirect_uris=["https://example.org/callback"]
        )
        self.client.patch.assert_called_once()
        self.client.put.assert_not_called()
        args, kwargs = self.client.patch.call_args
        self.assertEqual(args[0], "/auth/v1/clients/cid123/")
        self.assertEqual(
            kwargs["json"],
            {"redirect_uris": ["https://example.org/callback"]}
        )
        self.assertIsInstance(client, campus.model.Client)
        self.assertEqual(client.id, "cid123")
        self.assertEqual(client.name, "campus-cli")

    def test_update_omits_unset_fields(self):
        """PATCH bodies must carry only the fields being updated."""
        self.auth.clients["cid123"].update(name="new-name")
        self.assertEqual(
            self.client.patch.call_args.kwargs["json"],
            {"name": "new-name"}
        )


if __name__ == "__main__":
    unittest.main()
