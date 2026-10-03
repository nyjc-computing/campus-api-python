"""Tests for the query= parameter on non-GET JsonClient verbs.

get() has always taken query=; put/delete/patch gained it so callers
don't hand-build URLs when a non-GET endpoint reads the query string
(e.g. campus.auth's DELETE /auth/v1/connections/.../?user_id=...).
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")

from campus_python.json_client import CampusRequest


class TestQueryKwargOnNonGetVerbs(unittest.TestCase):
    """query= rides the session params on every verb, not just get()."""

    def setUp(self):
        self.client = CampusRequest(
            base_url="https://auth.example.test", mode="device"
        )

    def _assert_params_passed(self, verb: str, session_method: mock.Mock):
        self.client._timeout = 5
        with mock.patch.object(
                self.client._session, session_method,
                return_value=mock.Mock()) as method:
            getattr(self.client, verb)(
                "/some/path", json={"k": "v"}, query={"user_id": "u"})
        _, kwargs = method.call_args
        self.assertEqual(kwargs["json"], {"k": "v"})
        self.assertEqual(kwargs["params"], {"user_id": "u"})

    def test_put_passes_query_as_params(self):
        self._assert_params_passed("put", "put")

    def test_delete_passes_query_as_params(self):
        self._assert_params_passed("delete", "delete")

    def test_patch_passes_query_as_params(self):
        self._assert_params_passed("patch", "patch")

    def test_query_defaults_to_none(self):
        """Omitting query= sends params=None, preserving old behavior."""
        with mock.patch.object(
                self.client._session, "delete",
                return_value=mock.Mock()) as delete:
            self.client.delete("/some/path")
        self.assertIsNone(delete.call_args.kwargs["params"])


if __name__ == "__main__":
    unittest.main()
