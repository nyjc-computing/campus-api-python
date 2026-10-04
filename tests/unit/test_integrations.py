"""Tests for the integrations registry resource (issue #56).

client.integrations.list() hits the public auth-service catalog at
/integrations/v1/ (outside /auth/v1) and returns
campus.model.Integration entries.
"""

import unittest
from unittest.mock import Mock

import campus.model

import campus_python
from campus_python.integrations.v1 import IntegrationsRoot

REGISTRY_RESOURCE = {
    "integrations": [
        {
            "provider": "google.classroom",
            "slug": "classroom",
            "base_provider": "google",
            "title": "Google Classroom",
            "description": "Connect Google Classroom for coursework tooling.",
            "scopes": ["classroom.rosters"],
            "connectable": True,
            "authorize_path": "/auth/v1/google/classroom/authorize",
        },
        {
            "provider": "github",
            "slug": "github",
            "base_provider": "github",
            "title": "GitHub",
            "description": "Connect GitHub for repository tooling.",
            "scopes": [],
            "connectable": False,
            "authorize_path": "/auth/v1/github/github/authorize",
        },
    ]
}


def make_integrations() -> tuple[IntegrationsRoot, Mock]:
    """Create an IntegrationsRoot backed by a mock JSON client."""
    client = Mock()
    return IntegrationsRoot(json_client=client), client


class TestIntegrationsPaths(unittest.TestCase):
    """The registry resource must request its own API endpoint."""

    def setUp(self):
        self.integrations, _ = make_integrations()

    def test_list_path_is_top_level_versioned(self):
        """Registry sits at /integrations/v1/, not under /auth/v1."""
        self.assertEqual(self.integrations.make_path(), "/integrations/v1/")

    def test_url_prefix_keeps_trailing_slash(self):
        """The Flask route is GET /integrations/v1/ (trailing slash)."""
        self.assertTrue(self.integrations.make_path().endswith("/"))


class TestIntegrationsList(unittest.TestCase):
    """list() returns campus.model.Integration entries."""

    def setUp(self):
        self.integrations, self.client = make_integrations()
        self.client.get.return_value.json.return_value = REGISTRY_RESOURCE

    def test_list_requests_registry_endpoint(self):
        self.integrations.list()
        self.client.get.assert_called_once_with("/integrations/v1/")

    def test_list_returns_integration_models(self):
        result = self.integrations.list()
        self.assertEqual(len(result), 2)
        for item in result:
            self.assertIsInstance(item, campus.model.Integration)
        self.assertEqual(result[0].provider, "google.classroom")
        self.assertEqual(result[0].slug, "classroom")
        self.assertEqual(result[0].base_provider, "google")
        self.assertTrue(result[0].connectable)
        self.assertEqual(result[1].title, "GitHub")
        self.assertFalse(result[1].connectable)
        self.assertEqual(
            result[0].authorize_path,
            "/auth/v1/google/classroom/authorize",
        )

    def test_list_tolerates_missing_envelope_key(self):
        self.client.get.return_value.json.return_value = {}
        self.assertEqual(self.integrations.list(), [])


class TestCampusIntegrationsMounting(unittest.TestCase):
    """client.integrations is mounted on Campus and shares the auth client."""

    def test_integrations_mounted_on_campus(self):
        campus = campus_python.Campus(timeout=60, mode="device")
        self.assertIsInstance(campus.integrations, IntegrationsRoot)

    def test_integrations_shares_auth_client(self):
        """Registry is served by the auth service; reuse its client."""
        campus = campus_python.Campus(timeout=60, mode="device")
        self.assertIs(campus.integrations.client, campus.auth.client)

    def test_integrations_is_cached(self):
        campus = campus_python.Campus(timeout=60, mode="device")
        self.assertIs(campus.integrations, campus.integrations)
