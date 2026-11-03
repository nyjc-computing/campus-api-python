"""Unit tests for the CAMPUS_CLIENT_TIMEOUT resolution (tier-2 config).

Precedence: explicit constructor argument > CAMPUS_CLIENT_TIMEOUT env >
DEFAULT_CLIENT_TIMEOUT (60). Invalid env values fail open (default
applied, WARN logged) rather than breaking construction. Device mode
needs no credentials, so construction runs unmocked.
"""

import os
import unittest

from campus_python import DEFAULT_CLIENT_TIMEOUT, Campus


class TestClientTimeout(unittest.TestCase):
    """Campus(timeout=...) resolution order and fail-open behavior."""

    def setUp(self):
        self.saved = os.environ.get("CAMPUS_CLIENT_TIMEOUT")
        os.environ.pop("CAMPUS_CLIENT_TIMEOUT", None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self.saved is None:
            os.environ.pop("CAMPUS_CLIENT_TIMEOUT", None)
        else:
            os.environ["CAMPUS_CLIENT_TIMEOUT"] = self.saved

    def _construct(self, **kwargs):
        kwargs.setdefault("mode", "device")
        return Campus(**kwargs)

    def test_default_is_60_when_unset(self):
        campus = self._construct()
        self.assertEqual(campus.timeout, DEFAULT_CLIENT_TIMEOUT)
        self.assertEqual(campus.timeout, 60)

    def test_env_override(self):
        os.environ["CAMPUS_CLIENT_TIMEOUT"] = "15"
        campus = self._construct()
        self.assertEqual(campus.timeout, 15)

    def test_explicit_arg_wins_over_env(self):
        os.environ["CAMPUS_CLIENT_TIMEOUT"] = "15"
        campus = self._construct(timeout=90)
        self.assertEqual(campus.timeout, 90)

    def test_invalid_env_fails_open_with_default(self):
        os.environ["CAMPUS_CLIENT_TIMEOUT"] = "not-a-number"
        with self.assertLogs("campus_python", level="WARNING") as logs:
            campus = self._construct()
        self.assertEqual(campus.timeout, DEFAULT_CLIENT_TIMEOUT)
        self.assertTrue(any(
            "CAMPUS_CLIENT_TIMEOUT" in line for line in logs.output
        ))

    def test_nonpositive_env_fails_open_with_default(self):
        os.environ["CAMPUS_CLIENT_TIMEOUT"] = "0"
        campus = self._construct()
        self.assertEqual(campus.timeout, DEFAULT_CLIENT_TIMEOUT)

    def test_explicit_arg_survives_invalid_env(self):
        os.environ["CAMPUS_CLIENT_TIMEOUT"] = "garbage"
        campus = self._construct(timeout=45)
        self.assertEqual(campus.timeout, 45)


if __name__ == "__main__":
    unittest.main()
