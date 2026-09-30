"""Contract tests for model field types on parsed API resources
(client issue #37).

Model.from_resource() used to pass raw JSON values straight into the
dataclass constructor, so fields declared as schema types
(schema.DateTime, CampusID, ...) came back as plain str — violating the
models' own annotations. campus-cli relied on the declared types
(called .isoformat() on a created_at str; fixed defensively in
campus-cli PR #12).

campus weekly now coerces parsed values to their annotated schema types
(campus dfb7d0c for from_resource, ac9dfdc for from_storage; included in
the campus-suite 9e37b85 pinned by this repo). These tests pin that
contract so a campus-suite bump that regresses it fails here instead of
in campus-cli:

- str values for fields annotated as str subclasses (schema.DateTime,
  CampusID, Email) are coerced to the declared type and support the
  emulated helpers (to_datetime());
- fields annotated with plain builtins (str, bool, int) stay plain
  builtins;
- parsed models round-trip: to_resource() stays JSON-serialisable.
"""

import json
import unittest
from unittest.mock import Mock

import campus.common.schema as schema
import campus.model

from campus_python.auth.v1 import AuthRoot

# Exact client-resource shape emitted by campus weekly
# (Client.to_resource(): permissions/storage=False fields excluded,
# secret_hash resource=False).
CLIENT_RESOURCE = {
    "id": "cl_abc123",
    "created_at": "2026-09-30T06:31:24.582763+00:00",
    "name": "campus-cli",
    "description": "CLI client",
    "is_public": True,
    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
    "permissions": {},
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


class TestClientResourceFieldTypes(unittest.TestCase):
    """Client.from_resource() honours declared schema types (issue #37)."""

    def test_schema_typed_fields_are_coerced(self):
        client = campus.model.Client.from_resource(CLIENT_RESOURCE)
        self.assertIsInstance(client.id, schema.CampusID)
        self.assertIsInstance(client.created_at, schema.DateTime)

    def test_created_at_supports_emulated_datetime_helpers(self):
        """The DateTime helpers campus-cli needs must be available."""
        client = campus.model.Client.from_resource(CLIENT_RESOURCE)
        self.assertEqual(
            client.created_at.to_datetime().isoformat(),
            "2026-09-30T06:31:24.582763+00:00",
        )

    def test_plain_primitive_fields_unchanged(self):
        client = campus.model.Client.from_resource(CLIENT_RESOURCE)
        self.assertIs(type(client.name), str)
        self.assertIs(type(client.is_public), bool)
        # String subclass values still compare equal to the raw payload
        self.assertEqual(client.name, "campus-cli")

    def test_default_created_at_is_datetime(self):
        """Resources without created_at get the DateTime default factory."""
        payload = {k: v for k, v in CLIENT_RESOURCE.items() if k != "created_at"}
        client = campus.model.Client.from_resource(payload)
        self.assertIsInstance(client.created_at, schema.DateTime)

    def test_to_resource_round_trips_json_serialisable(self):
        client = campus.model.Client.from_resource(CLIENT_RESOURCE)
        self.assertEqual(json.loads(json.dumps(client.to_resource())),
                         CLIENT_RESOURCE)


class TestUserResourceFieldTypes(unittest.TestCase):
    """Other schema-typed fields get the same treatment (issue #37)."""

    def test_email_field_is_coerced(self):
        user = campus.model.User.from_resource({
            "id": "us_abc123",
            "created_at": "2026-09-30T06:31:24.582763+00:00",
            "email": "alice@nyjc.edu.sg",
            "name": "Alice",
        })
        self.assertIsInstance(user.email, schema.Email)
        self.assertEqual(user.email.domain, "nyjc.edu.sg")
        self.assertIsInstance(user.created_at, schema.DateTime)


class TestOAuthTokenFieldTypes(unittest.TestCase):
    """Nested OAuthToken resources carry coerced DateTime fields too."""

    def test_nested_token_datetimes_are_coerced(self):
        creds = campus.model.UserCredentials.from_resource(CREDENTIALS_RESOURCE)
        self.assertIsInstance(creds.created_at, schema.DateTime)
        self.assertIsInstance(creds.token, campus.model.OAuthToken)
        self.assertIsInstance(creds.token.created_at, schema.DateTime)
        self.assertIsInstance(creds.token.expires_at, schema.DateTime)
        # Plain primitives stay plain
        self.assertIs(type(creds.token.expires_in), int)


class TestClientSurfacePaths(unittest.TestCase):
    """The models this client returns to consumers carry schema types."""

    def test_clients_new_returns_coerced_model(self):
        resp = Mock()
        resp.json.return_value = CLIENT_RESOURCE
        client = Mock()
        client.post.return_value = resp
        auth = AuthRoot(json_client=client)

        created = auth.clients.new(name="campus-cli", description="CLI client")
        self.assertIsInstance(created, campus.model.Client)
        self.assertIsInstance(created.created_at, schema.DateTime)

    def test_clients_get_returns_coerced_model(self):
        resp = Mock()
        resp.json.return_value = CLIENT_RESOURCE
        client = Mock()
        client.get.return_value = resp
        auth = AuthRoot(json_client=client)

        fetched = auth.clients["cl_abc123"].get()
        self.assertIsInstance(fetched, campus.model.Client)
        self.assertIsInstance(fetched.created_at, schema.DateTime)
        self.assertIsInstance(fetched.id, schema.CampusID)


if __name__ == "__main__":
    unittest.main()
