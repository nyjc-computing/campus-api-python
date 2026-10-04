"""Contract tests for the auth coverage remainder (issue #76).

- Clients.Client.access.check() — GET /auth/v1/clients/<id>/access/check
  (leaf path, no trailing slash; vault/permission as query params)
- Clients.new() — POST /auth/v1/clients/ also accepts allowed_scopes,
  upstream_scopes, token_bridge (as the server route does)
- Credentials.Provider.User.new() — POST /auth/v1/credentials/
  <provider>/<user_id> with {scopes, expires_in}; the client_id comes
  from the request's auth context, not the body
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
    "name": "campus-app",
    "description": "Server-mode app",
    "is_public": False,
    "redirect_uris": [],
}

# UserCredentials resource (scope-only token emission, campus #657).
CREDENTIALS_RESOURCE = {
    "id": "cred1",
    "created_at": "2026-09-30T06:31:24.582763+00:00",
    "provider": "campus",
    "client_id": "cid123",
    "user_id": "user1",
    "token": {
        "id": "tok123",
        "created_at": "2026-09-30T06:31:24.582763+00:00",
        "expires_at": "2026-09-30T07:31:24.582763+00:00",
        "expires_in": 3600,
        "token_type": "Bearer",
        "refresh_token": "rt123",
        "refresh_token_expires_at": None,
        "scope": "campus.profile campus.identities",
    },
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


class TestClientAccessCheck(unittest.TestCase):
    """access.check() must GET the /access/check leaf route."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.get.return_value.json.return_value = {
            "vault": "campus.vault", "permission": True
        }

    def test_check_sends_vault_and_permission_as_query(self):
        result = self.auth.clients["cid123"].access.check(
            vault="campus.vault", permission=3
        )
        self.client.get.assert_called_once_with(
            "/auth/v1/clients/cid123/access/check",
            query={"vault": "campus.vault", "permission": 3},
        )
        self.assertEqual(result, {"vault": "campus.vault", "permission": True})


class TestClientsNewScopeFields(unittest.TestCase):
    """Clients.new() must forward the scope/bridge registration fields."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.post.return_value.json.return_value = CLIENT_RESOURCE

    def test_new_sends_scope_fields_when_given(self):
        self.auth.clients.new(
            name="campus-app",
            description="Server-mode app",
            allowed_scopes=["campus.api"],
            upstream_scopes={"google": ["https://www.googleapis.com/auth/calendar"]},
            token_bridge=True,
        )
        self.assertEqual(
            self.client.post.call_args.kwargs["json"],
            {
                "name": "campus-app",
                "description": "Server-mode app",
                "is_public": False,
                "redirect_uris": [],
                "allowed_scopes": ["campus.api"],
                "upstream_scopes": {
                    "google": ["https://www.googleapis.com/auth/calendar"]
                },
                "token_bridge": True,
            },
        )

    def test_new_omits_unset_scope_fields(self):
        self.auth.clients.new(name="campus-app", description="d")
        self.assertEqual(
            self.client.post.call_args.kwargs["json"],
            {
                "name": "campus-app",
                "description": "d",
                "is_public": False,
                "redirect_uris": [],
            },
        )


class TestCredentialsUserNew(unittest.TestCase):
    """User.new() must POST the live endpoint instead of raising."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.post.return_value.json.return_value = CREDENTIALS_RESOURCE

    def test_new_posts_scopes_and_expires_in(self):
        creds = self.auth.credentials["campus"]["user1"].new(
            scopes=["campus.profile"], expires_in=3600
        )
        self.client.post.assert_called_once_with(
            "/auth/v1/credentials/campus/user1",
            json={"scopes": ["campus.profile"], "expires_in": 3600},
        )
        self.assertIsInstance(creds, campus.model.UserCredentials)
        self.assertEqual(creds.token.id, "tok123")


if __name__ == "__main__":
    unittest.main()
