"""Tests for Campus service base URL resolution.

Pins the contract for issue #52: explicit URL config (CAMPUS_AUTH_URL /
CAMPUS_API_URL) takes precedence over ENV-based defaults, and settings
that previously produced HOSTNAME-derived URLs (DEPLOY service suffix,
ENV/CAMPUS_ENV=testing) emit a DeprecationWarning and fall back to the
ENV-based default instead.
"""

import os
import unittest
import warnings

import campus_python

AUTH_DEV_URL = "https://campusauth-development.up.railway.app"
API_DEV_URL = "https://campusapi-development.up.railway.app"

# All env vars that influence URL resolution
URL_VARS = ("CAMPUS_AUTH_URL", "CAMPUS_API_URL", "ENV", "CAMPUS_ENV", "DEPLOY")


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
        # api service is unaffected
        self.assertEqual(campus.api.base_url, API_DEV_URL)

    def test_explicit_api_url(self):
        os.environ["CAMPUS_API_URL"] = "http://localhost:8000"
        campus = self.new_client()
        self.assertEqual(campus.api.base_url, "http://localhost:8000")
        # auth service is unaffected
        self.assertEqual(campus.auth.base_url, AUTH_DEV_URL)

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


class TestEnvDefaults(BaseUrlResolutionTestCase):
    """ENV/CAMPUS_ENV-based defaults when no explicit URL is set."""

    def test_development_default(self):
        campus = self.new_client()
        self.assertEqual(campus.auth.base_url, AUTH_DEV_URL)
        self.assertEqual(campus.api.base_url, API_DEV_URL)

    def test_staging_default(self):
        os.environ["ENV"] = "staging"
        campus = self.new_client()
        self.assertEqual(campus.auth.base_url, "https://auth.campus.nyjc.dev")
        self.assertEqual(campus.api.base_url, "https://api.campus.nyjc.dev")

    def test_production_default(self):
        os.environ["ENV"] = "production"
        campus = self.new_client()
        self.assertEqual(campus.auth.base_url, "https://auth.campus.nyjc.app")
        self.assertEqual(campus.api.base_url, "https://api.campus.nyjc.app")

    def test_campus_env_alias(self):
        os.environ["CAMPUS_ENV"] = "staging"
        campus = self.new_client()
        self.assertEqual(campus.auth.base_url, "https://auth.campus.nyjc.dev")
        self.assertEqual(campus.api.base_url, "https://api.campus.nyjc.dev")

    def test_invalid_env_raises(self):
        os.environ["ENV"] = "nonsense"
        campus = self.new_client()
        with self.assertRaises(ValueError):
            campus.auth


class TestHostnameDeprecation(BaseUrlResolutionTestCase):
    """Settings that previously produced HOSTNAME-derived URLs now warn."""

    def test_testing_env_warns_and_falls_back_to_development(self):
        os.environ["ENV"] = "testing"
        campus = self.new_client()
        with self.assertWarns(DeprecationWarning):
            campus.auth
            campus.api
        self.assertEqual(campus.auth.base_url, AUTH_DEV_URL)
        self.assertEqual(campus.api.base_url, API_DEV_URL)

    def test_deploy_auth_suffix_warns(self):
        os.environ["DEPLOY"] = "campus.auth"
        campus = self.new_client()
        with self.assertWarns(DeprecationWarning):
            campus.auth
        # Falls back to the ENV-based default (development)
        self.assertEqual(campus.auth.base_url, AUTH_DEV_URL)
        # api service did not match the .auth suffix: no HOSTNAME URL before
        self.assertEqual(campus.api.base_url, API_DEV_URL)

    def test_deploy_api_suffix_warns(self):
        os.environ["DEPLOY"] = "campus.api"
        campus = self.new_client()
        with self.assertWarns(DeprecationWarning):
            campus.api
        self.assertEqual(campus.api.base_url, API_DEV_URL)
        self.assertEqual(campus.auth.base_url, AUTH_DEV_URL)

    def test_warning_mentions_url_var(self):
        os.environ["ENV"] = "testing"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.new_client().auth
        deprecations = [
            w for w in caught
            if issubclass(w.category, DeprecationWarning)
        ]
        self.assertEqual(len(deprecations), 1)
        self.assertIn("CAMPUS_AUTH_URL", str(deprecations[0].message))

    def test_unrelated_deploy_value_no_warning(self):
        # A DEPLOY value without a service suffix never produced HOSTNAME URLs
        os.environ["DEPLOY"] = "campus.other"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            campus = self.new_client()
        deprecations = [
            w for w in caught
            if issubclass(w.category, DeprecationWarning)
        ]
        self.assertEqual(deprecations, [])
        self.assertEqual(campus.auth.base_url, AUTH_DEV_URL)


if __name__ == "__main__":
    unittest.main()
