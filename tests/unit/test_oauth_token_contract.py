"""Contract tests for OAuth token flows against the RFC 6749-compliant
OAuthToken interface (campus issue #648, PRs #650/#654; client issue #40).

campus #650 aligned OAuthToken with RFC 6749 token semantics. These tests
pin the wire shapes exchanged with the dev API (campus-suite, branch
weekly) so the client stays compatible until campus lands its deprecation
PR:

- POST /auth/v1/oauth/token responses carry standard RFC keys (access_token,
  token_type, expires_in, scope) which OAuthToken.from_resource maps to
  campus names;
- GET /credentials/... resources nest the token carrying the RFC 6749
  `scope` string only (scope-only emission since campus #657);
  from_resource still accepts legacy `scopes` lists;
- PATCH /credentials/... bodies are validated server-side via
  OAuthToken.from_resource() (campus #656), which maps the RFC 6749
  `scope` string to `scopes` and bags unknown provider keys into
  provider_fields; User.update() sends the full to_resource() output;
- the legacy `expiry_seconds` alias is fully removed (campus #659,
  #648 checklist item 2): the constructor rejects the kwarg and
  payloads whose only expiry information is `expiry_seconds` fail
  validation — `expires_in` is the only accepted form.
"""

import os
import unittest
from unittest.mock import Mock, patch

import campus.model

from campus_python.auth.v1 import AuthRoot

# Exact token-endpoint response shape emitted by campus weekly
# (device-code grant in campus/auth/routes/oauth.py; client_credentials
# and refresh_token grants are equivalent RFC payloads).
RFC_TOKEN_PAYLOAD = {
    "access_token": "tok123",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "rt123",
    "scope": "campus.profile campus.identities",
}

# Exact credentials-resource shape emitted by campus weekly
# (UserCredentials.to_resource() with its nested OAuthToken token;
# scope-only token emission since campus #657).
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


class TestTokenEndpointDeserialization(unittest.TestCase):
    """auth.token() / _exchange_code_for_token() consume RFC payloads."""

    def test_rfc_token_payload_deserializes(self):
        token = campus.model.OAuthToken.from_resource(RFC_TOKEN_PAYLOAD)
        self.assertEqual(token.id, "tok123")
        self.assertEqual(token.access_token, token.id)
        self.assertEqual(token.token_type, "Bearer")
        self.assertEqual(token.expires_in, 3600)
        self.assertEqual(token.scopes, ["campus.profile", "campus.identities"])
        self.assertEqual(token.scope, "campus.profile campus.identities")
        self.assertEqual(token.refresh_token, "rt123")

    def test_token_type_is_case_normalised(self):
        payload = dict(RFC_TOKEN_PAYLOAD, token_type="bearer")
        token = campus.model.OAuthToken.from_resource(payload)
        self.assertEqual(token.token_type, "Bearer")

    def test_legacy_token_resource_deserializes(self):
        """Records without the new fields still construct (compat window)."""
        token = campus.model.OAuthToken.from_resource({
            "id": "tok-legacy",
            "created_at": "2026-09-30T00:00:00Z",
            "expires_at": "2026-09-30T01:00:00Z",
            "scopes": ["campus.profile"],
        })
        self.assertEqual(token.id, "tok-legacy")
        self.assertEqual(token.token_type, "Bearer")
        self.assertEqual(token.expires_in, 3600)
        self.assertEqual(token.scopes, ["campus.profile"])


class TestCredentialsResourceDeserialization(unittest.TestCase):
    """UserCredentials.from_resource() must consume the nested token."""

    def test_nested_token_deserializes(self):
        creds = campus.model.UserCredentials.from_resource(CREDENTIALS_RESOURCE)
        self.assertEqual(creds.provider, "campus")
        self.assertEqual(creds.user_id, "user1")
        self.assertIsInstance(creds.token, campus.model.OAuthToken)
        self.assertEqual(creds.token.id, "tok123")
        self.assertEqual(creds.token.token_type, "Bearer")
        self.assertEqual(creds.token.expires_in, 3600)
        self.assertEqual(creds.token.scopes, ["campus.profile", "campus.identities"])
        self.assertEqual(creds.token.scope, "campus.profile campus.identities")


class TestCredentialsUpdatePatchBody(unittest.TestCase):
    """User.update() must send a body the server's
    OAuthToken.from_resource() validation accepts
    (campus/auth/routes/credentials.py, campus #656)."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.token = campus.model.OAuthToken(
            id="tok123",
            expires_in=3600,
            scopes=["campus.profile", "campus.identities"],
            refresh_token="rt123",
        )

    def test_update_patches_credentials_endpoint(self):
        with patch.dict(os.environ, {"CLIENT_ID": "cid123"}):
            self.auth.credentials["campus"]["user1"].update(self.token)
        self.client.patch.assert_called_once()
        args, kwargs = self.client.patch.call_args
        self.assertEqual(args[0], "/auth/v1/credentials/campus/user1")
        self.assertEqual(kwargs["json"]["client_id"], "cid123")
        self.assertEqual(kwargs["json"]["token"], self.token.to_resource())

    def test_patch_body_passes_server_validation(self):
        """The sent token payload must pass OAuthToken.from_resource().

        Mirrors the server-side validation (campus #656). Token
        resources emit `scope` only since campus #657 (deprecation
        checklist item 4); from_resource maps it back to `scopes`.
        """
        with patch.dict(os.environ, {"CLIENT_ID": "cid123"}):
            self.auth.credentials["campus"]["user1"].update(self.token)
        body = self.client.patch.call_args.kwargs["json"]
        sent_token = body["token"]
        self.assertIn("scope", sent_token)
        self.assertNotIn("scopes", sent_token)
        validated = campus.model.OAuthToken.from_resource(sent_token)
        self.assertEqual(validated.id, "tok123")
        self.assertEqual(validated.scopes, ["campus.profile", "campus.identities"])
        self.assertEqual(validated.scope, "campus.profile campus.identities")

    def test_scope_only_payload_passes_server_validation(self):
        """A scope-only payload — the token resource shape expected once
        the campus #648 deprecation window closes — also passes the
        server's from_resource() validation."""
        scope_only = {
            "access_token": "tok456",
            "expires_in": 3600,
            "scope": "campus.profile",
        }
        validated = campus.model.OAuthToken.from_resource(scope_only)
        self.assertEqual(validated.id, "tok456")
        self.assertEqual(validated.scopes, ["campus.profile"])
        self.assertEqual(validated.scope, "campus.profile")


class TestTokenEndpointPath(unittest.TestCase):
    """auth.token() must target the RFC 6749 token endpoint
    (/auth/v1/oauth/token, campus/auth/routes/oauth.py), not the
    authorization-code session endpoint at /auth/v1/token
    (campus/auth/provider.py) — whose contract requires code and
    redirect_uri and rejects every other grant type (client issue #60).
    """

    def setUp(self):
        self.auth, self.client = make_auth()
        self.client.base_url = ""
        self.client.post.return_value.json.return_value = dict(
            RFC_TOKEN_PAYLOAD
        )

    def test_client_credentials_targets_oauth_token_endpoint(self):
        envvars = {"CLIENT_ID": "cid123", "CLIENT_SECRET": "sec123"}
        with patch.dict(os.environ, envvars):
            self.auth.token(grant_type="client_credentials")

        args, kwargs = self.client.post.call_args
        self.assertEqual(args[0], "/auth/v1/oauth/token")
        self.assertEqual(kwargs["json"]["grant_type"], "client_credentials")
        self.assertEqual(kwargs["json"]["client_id"], "cid123")
        self.assertEqual(kwargs["json"]["client_secret"], "sec123")

    def test_refresh_token_targets_oauth_token_endpoint(self):
        self.auth.token(grant_type="refresh_token", refresh_token="rt123")

        args, kwargs = self.client.post.call_args
        self.assertEqual(args[0], "/auth/v1/oauth/token")
        self.assertEqual(kwargs["json"]["grant_type"], "refresh_token")
        self.assertEqual(kwargs["json"]["refresh_token"], "rt123")


class TestExpirySecondsAliasRemoved(unittest.TestCase):
    """The legacy `expiry_seconds` alias is gone (campus #659, closing
    #648 checklist item 2). The client has no call sites; these pins
    guard against it creeping back in either direction."""

    def test_constructor_rejects_expiry_seconds_kwarg(self):
        with self.assertRaises(TypeError):
            campus.model.OAuthToken(id="tok-1", expiry_seconds=60)

    def test_payload_with_only_expiry_seconds_fails_validation(self):
        """Mirrors the server-side validation: a payload whose only
        expiry information is the removed legacy key cannot construct,
        so the server answers 422 VALIDATION_FAILED."""
        with self.assertRaises(ValueError):
            campus.model.OAuthToken.from_resource({
                "access_token": "tok-2",
                "expiry_seconds": 60,
            })


if __name__ == "__main__":
    unittest.main()
