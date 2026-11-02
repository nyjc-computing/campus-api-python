"""Tests for Campus service base URL resolution.

Pins the env-only contract (campus-common 0.3.0): the environment is
the source of truth — CAMPUS_<SERVICE>_URL > <SERVICE>_URL >
CAMPUS_BASE_URL > BASE_URL — Campus ships no baked-in topology, so an
unconfigured service raises ValueError instead of falling back to
hardcoded origins.
"""

import os
import unittest
import warnings

import campus_python

AUTH_DEV_URL = "https://campusauth-development.up.railway.app"
API_DEV_URL = "https://campusapi-development.up.railway.app"

# All env vars that influence URL resolution
URL_VARS = (
    "CAMPUS_AUTH_URL", "AUTH_URL",
    "CAMPUS_API_URL", "API_URL",
    "CAMPUS_AUDIT_URL", "AUDIT_URL",
    "CAMPUS_BASE_URL", "BASE_URL",
    "ENV", "CAMPUS_ENV", "DEPLOY",
)


class BaseUrlResolutionTestCase(unittest.TestCase):
    """Base test case that saves and clears URL-related env vars."""

    def setUp(self):
        self.saved = {var: os.environ.get(var) for var in URL_VARS}
        for var in URL_VARS:
            os.environ.pop(var, None)

    def tearDown(self):
        for var, value in self.saved.items():
            if value is not None:
                os.environ[var] = value
            else:
                os.environ.pop(var, None)

    def new_client(self) -> campus_python.Campus:
        """Create a device-mode client (no credentials required)."""
        return campus_python.Campus(timeout=5, mode="device")


class TestExplicitUrlConfig(BaseUrlResolutionTestCase):
    """Explicit URL config takes precedence over ENV-based defaults."""

    def test_explicit_auth_url(self):
        os.environ["CAMPUS_AUTH_URL"] = "https://auth.example.com"
        campus = self.new_client()
        self.assertEqual(campus.auth.base_url, "https://auth.example.com")
        # api service is unconfigured: no invented URLs
        with self.assertRaises(ValueError):
            campus.api

    def test_explicit_api_url(self):
        os.environ["CAMPUS_API_URL"] = "http://localhost:8000"
        campus = self.new_client()
        self.assertEqual(campus.api.base_url, "http://localhost:8000")
        # auth service is unconfigured: no invented URLs
        with self.assertRaises(ValueError):
            campus.auth

    def test_explicit_url_overrides_env_default(self):
        os.environ["ENV"] = "production"
        os.environ["CAMPUS_AUTH_URL"] = "https://auth.example.com"
        os.environ["CAMPUS_API_URL"] = "https://api.example.com"
        campus = self.new_client()
        self.assertEqual(campus.auth.base_url, "https://auth.example.com")
        self.assertEqual(campus.api.base_url, "https://api.example.com")

    def test_explicit_url_no_deprecation_warning(self):
        # Even with legacy settings present, explicit config is not deprecated
        os.environ["ENV"] = "testing"
        os.environ["DEPLOY"] = "campus.auth"
        os.environ["CAMPUS_AUTH_URL"] = "http://localhost:5000"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            campus = self.new_client()
            campus.auth
        deprecations = [
            w for w in caught
            if issubclass(w.category, DeprecationWarning)
        ]
        self.assertEqual(deprecations, [])
        self.assertEqual(campus.auth.base_url, "http://localhost:5000")


class TestBaseConfig(BaseUrlResolutionTestCase):
    """Gateway base URL applies to every service; no ENV-tier defaults."""

    def test_base_url_applies_to_all_services(self):
        os.environ["BASE_URL"] = "https://gateway.example"
        campus = self.new_client()
        self.assertEqual(campus.auth.base_url, "https://gateway.example")
        self.assertEqual(campus.api.base_url, "https://gateway.example")

    def test_unconfigured_service_raises(self):
        # No baked-in topology: env is the source of truth.
        campus = self.new_client()
        with self.assertRaisesRegex(ValueError, "CAMPUS_AUTH_URL"):
            campus.auth

    def test_testing_env_without_config_still_raises(self):
        os.environ["ENV"] = "testing"
        campus = self.new_client()
        with self.assertRaises(ValueError):
            campus.auth


if __name__ == "__main__":
    unittest.main()
