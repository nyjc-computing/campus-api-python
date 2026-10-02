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

# The scope/bridge admin fields (campus-cli#24) as the PATCH response
# carries them once set.
CLIENT_RESOURCE_WITH_SCOPES = {
    **CLIENT_RESOURCE,
    "allowed_scopes": ["openid", "campus.api"],
    "upstream_scopes": {
        "google": ["https://www.googleapis.com/auth/calendar"],
        "google.classroom": [
            "https://www.googleapis.com/auth/classroom.rosters",
        ],
    },
    "token_bridge": True,
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


class TestClientsUpdateScopeBridgeFields(unittest.TestCase):
    """Clients.Client.update() forwards the scope/bridge admin fields
    (campus-cli#24): allowed_scopes, upstream_scopes and token_bridge.

    The server PATCH full-replaces each provided field, so the SDK
    must send exactly what the caller passed, and nothing for fields
    left unset.
    """

    def setUp(self):
        self.auth, self.client = make_auth()
        response = Mock()
        response.json.return_value = CLIENT_RESOURCE_WITH_SCOPES
        self.client.patch.return_value = response

    def test_update_forwards_scope_bridge_fields(self):
        """All three fields are forwarded verbatim when passed."""
        allowed = ["openid", "campus.api"]
        upstream = {"google": ["https://www.googleapis.com/auth/calendar"]}
        client = self.auth.clients["cid123"].update(
            allowed_scopes=allowed,
            upstream_scopes=upstream,
            token_bridge=True,
        )
        self.assertEqual(
            self.client.patch.call_args.kwargs["json"],
            {
                "allowed_scopes": allowed,
                "upstream_scopes": upstream,
                "token_bridge": True,
            }
        )
        # The mocked response payload is CLIENT_RESOURCE_WITH_SCOPES;
        # from_resource must absorb all three fields from it.
        self.assertEqual(
            client.allowed_scopes,
            CLIENT_RESOURCE_WITH_SCOPES["allowed_scopes"]
        )
        self.assertEqual(
            client.upstream_scopes,
            CLIENT_RESOURCE_WITH_SCOPES["upstream_scopes"]
        )
        self.assertTrue(client.token_bridge)

    def test_update_forwards_no_token_bridge_false(self):
        """--no-token-bridge style updates send token_bridge=False."""
        response = Mock()
        response.json.return_value = {**CLIENT_RESOURCE, "token_bridge": False}
        self.client.patch.return_value = response
        self.auth.clients["cid123"].update(token_bridge=False)
        self.assertEqual(
            self.client.patch.call_args.kwargs["json"],
            {"token_bridge": False}
        )

    def test_update_omits_scope_bridge_fields_when_unset(self):
        """Unset scope/bridge fields stay out of the PATCH body."""
        self.auth.clients["cid123"].update(name="new-name")
        body = self.client.patch.call_args.kwargs["json"]
        self.assertEqual(body, {"name": "new-name"})
        self.assertNotIn("allowed_scopes", body)
        self.assertNotIn("upstream_scopes", body)
        self.assertNotIn("token_bridge", body)

    def test_update_empty_allowed_scopes_is_sent(self):
        """An explicit empty allowlist must not be dropped: fail-closed
        A1 means an empty list grants nothing, so clearing is a real
        operation the admin may need to send.
        """
        response = Mock()
        response.json.return_value = {**CLIENT_RESOURCE, "allowed_scopes": []}
        self.client.patch.return_value = response
        self.auth.clients["cid123"].update(allowed_scopes=[])
        self.assertEqual(
            self.client.patch.call_args.kwargs["json"],
            {"allowed_scopes": []}
        )


if __name__ == "__main__":
    unittest.main()
