"""Unit tests for the audit client credential handling.

Verifies that AuditClient sends the AUDIT_API_KEY as explicit Bearer
auth (scoped to the audit client only), falling back to ambient
CLIENT_ID/CLIENT_SECRET only when no key is set (#699).

Ported from the flask-campus dist's campus.audit.client tests
(flask-campus#31): the middleware-side credential-singleton tests stay
with the middleware in flask-campus.

File: tests/unit/test_audit_client.py
Issue: #699, flask-campus#31
"""

import os
import unittest

from campus_python.audit.client import AuditClient


def _set_env(test: unittest.TestCase, name: str, value: str) -> None:
    """Set an env var for the duration of a test."""
    os.environ[name] = value
    test.addCleanup(os.environ.pop, name, None)


def _del_env(test: unittest.TestCase, name: str) -> None:
    """Unset an env var for the duration of a test."""
    saved = os.environ.pop(name, None)

    def restore():
        if saved is not None:
            os.environ[name] = saved

    test.addCleanup(restore)


class TestCreateHttpClientAuth(unittest.TestCase):
    """Verify _create_http_client auth priority (#699)."""

    def setUp(self):
        # Save/restore test-injection attribute in case another suite set it
        self._saved_client_class = AuditClient.json_client_class
        self.addCleanup(setattr, AuditClient, "json_client_class", self._saved_client_class)
        AuditClient.json_client_class = None

    def test_api_key_sends_explicit_bearer(self):
        """AUDIT_API_KEY produces a Bearer Authorization header."""
        from campus_python.audit.client import _create_http_client
        from campus_python.audit.http import DefaultClient

        _set_env(self, "AUDIT_API_KEY", "audit_v1_abcdefghijklmnopqrstuvwxyz")
        client = _create_http_client("https://audit.test")
        self.assertIsInstance(client, DefaultClient)
        self.assertEqual(
            client.headers["Authorization"],
            "Bearer audit_v1_abcdefghijklmnopqrstuvwxyz"
        )

    def test_api_key_ignores_ambient_credentials(self):
        """AUDIT_API_KEY wins over ambient ACCESS_TOKEN/CLIENT_ID env.

        The explicit auth path must not inherit the shared ambient
        credentials used by other DefaultClient consumers (#699).
        """
        from campus_python.audit.client import _create_http_client

        _set_env(self, "AUDIT_API_KEY", "audit_v1_abcdefghijklmnopqrstuvwxyz")
        _set_env(self, "ACCESS_TOKEN", "ambient-access-token")
        _set_env(self, "CLIENT_ID", "uid-client-ambient")
        _set_env(self, "CLIENT_SECRET", "ambient-secret")
        client = _create_http_client("https://audit.test")
        self.assertEqual(
            client.headers["Authorization"],
            "Bearer audit_v1_abcdefghijklmnopqrstuvwxyz"
        )

    def test_without_api_key_falls_back_to_ambient_basic(self):
        """Without AUDIT_API_KEY, ambient CLIENT_ID/CLIENT_SECRET apply."""
        from campus_python.audit.client import _create_http_client
        from campus_python.audit.http import DefaultClient

        _del_env(self, "AUDIT_API_KEY")
        _del_env(self, "ACCESS_TOKEN")
        _set_env(self, "CLIENT_ID", "uid-client-legacy")
        _set_env(self, "CLIENT_SECRET", "legacy-secret")
        client = _create_http_client("https://audit.test")
        self.assertIsInstance(client, DefaultClient)
        self.assertTrue(client.headers["Authorization"].startswith("Basic "))

    def test_json_client_class_takes_priority(self):
        """Test-injection json_client_class wins over AUDIT_API_KEY."""

        class StubClient:
            def __init__(self, base_url: str):
                self.base_url = base_url

        AuditClient.json_client_class = StubClient  # type: ignore[assignment]
        _set_env(self, "AUDIT_API_KEY", "audit_v1_abcdefghijklmnopqrstuvwxyz")
        client = AuditClient(base_url="https://audit.test")
        self.assertIsInstance(client._root._client, StubClient)


if __name__ == "__main__":
    unittest.main()
