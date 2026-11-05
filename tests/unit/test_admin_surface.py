"""Unit tests for the #1055 admin surface (campus#1055).

The campus auth service grew an admin surface: GET /sessions/ (the
provider-agnostic enumeration), redacted credential reads with a
per-record ?include=token opt-in, disconnect-by-client-id, and GET
/vaults/ label enumeration. The SDK methods must hit the new paths
and shapes exactly.
"""

import os
import unittest
from tests.support import make_auth

os.environ.setdefault("CLIENT_ID", "test-client-id")


class TestSessionsList(unittest.TestCase):
    """CampusSessions.list() hits /sessions/, not the campus-provider
    path the collection wraps."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def test_list_hits_provider_agnostic_path(self):
        self.client.get.return_value.json.return_value = {"sessions": [], "total": 0}
        self.auth.sessions.list()
        self.client.get.assert_called_once_with(
            "/auth/v1/sessions/",
            query={"provider": "campus"},
        )

    def test_list_builds_filters_and_pagination(self):
        self.client.get.return_value.json.return_value = {"sessions": [], "total": 0}
        self.auth.sessions.list(
            client_id="client_1",
            user_id="user@campus.test",
            limit=50,
            offset=10,
        )
        self.client.get.assert_called_once_with(
            "/auth/v1/sessions/",
            query={
                "provider": "campus",
                "client_id": "client_1",
                "user_id": "user@campus.test",
                "limit": 50,
                "offset": 10,
            },
        )

    def test_list_parses_session_records(self):
        record = {
            "id": "uid-campus_session-1",
            "provider": "campus",
            "client_id": "client_1",
            "redirect_uri": "https://example.com/callback",
            "created_at": "2026-11-04T00:00:00+00:00",
            "expires_at": "2026-11-04T01:00:00+00:00",
        }
        self.client.get.return_value.json.return_value = {
            "sessions": [record], "total": 1,
        }
        sessions = self.auth.sessions.list()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, record["id"])


class TestCredentialsRedaction(unittest.TestCase):
    """The include_token opt-in rides the query on per-record reads
    only, and delete() can target another client's record."""

    def setUp(self):
        self.auth, self.client = make_auth()
        # UserCredentials requires its keying fields on from_resource.
        self.cred_record = {
            "id": "uid-credential-1",
            "provider": "campus",
            "client_id": "test-client-id",
            "user_id": "user@campus.test",
            "created_at": "2026-11-04T00:00:00+00:00",
            "token": None,
        }

    def test_get_defaults_to_redacted_read(self):
        self.client.get.return_value.json.return_value = self.cred_record
        self.auth.credentials["campus"].get("tok_123")
        self.client.get.assert_called_once_with(
            "/auth/v1/credentials/campus/",
            query={"token_id": "tok_123"},
        )

    def test_get_include_token_opt_in(self):
        self.client.get.return_value.json.return_value = self.cred_record
        self.auth.credentials["campus"].get("tok_123", include_token=True)
        self.client.get.assert_called_once_with(
            "/auth/v1/credentials/campus/",
            query={"token_id": "tok_123", "include": "token"},
        )

    def test_user_get_include_token_opt_in(self):
        self.client.get.return_value.json.return_value = self.cred_record
        self.auth.credentials["campus"]["user@campus.test"].get(
            include_token=True
        )
        self.client.get.assert_called_once_with(
            "/auth/v1/credentials/campus/user@campus.test/",
            query={"client_id": "test-client-id", "include": "token"},
        )

    def test_delete_targets_another_clients_record(self):
        self.auth.credentials["campus"]["user@campus.test"].delete(
            client_id="client_other"
        )
        self.client.delete.assert_called_once_with(
            "/auth/v1/credentials/campus/user@campus.test/",
            json={"client_id": "client_other"},
        )


class TestVaultLabels(unittest.TestCase):
    """Vaults.labels() hits GET /vaults/ (the collection path itself)."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def test_labels_parses_enumeration(self):
        self.client.get.return_value.json.return_value = {
            "labels": ["apps", "storage", "vault"]
        }
        labels = self.auth.vaults.labels()
        self.client.get.assert_called_once_with("/auth/v1/vaults/")
        self.assertEqual(labels, ["apps", "storage", "vault"])

    def test_labels_tolerates_missing_key(self):
        self.client.get.return_value.json.return_value = {}
        self.assertEqual(self.auth.vaults.labels(), [])


if __name__ == "__main__":
    unittest.main()
