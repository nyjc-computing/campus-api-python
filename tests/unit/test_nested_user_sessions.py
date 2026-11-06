"""Nested with_user_session must preserve the outer session (#159).

The auth-broker release runs a with_user_session inside a route that
already holds one (campus-classroom's enrollment bridge): the inner
teardown used to reset the shared clients to app Basic credentials, so
the outer session's subsequent campus.api calls went out as the app's
client principal. These tests pin the nesting-safe teardown.

Device mode keeps the tests off the network; the login-session token
acquisition is patched per test. Client env credentials are set so the
teardown's reset_authorization() (entry state None → revoke) works.
"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")

from campus_python import Campus


def make_api():
    """Device-mode Campus + a patcher faking the login-session token."""
    # The auth/api clients resolve base URLs lazily; the token call is
    # patched, so a stub origin is enough.
    os.environ["CAMPUS_AUTH_URL"] = "http://localhost"
    os.environ["CAMPUS_API_URL"] = "http://localhost"
    campus = Campus(mode="device")

    def patch_token(name):
        return mock.patch.object(
            campus.auth.logins, "token",
            return_value=SimpleNamespace(access_token=f"tok-{name}"),
        )

    return campus, patch_token


class TestNestedUserSessions(unittest.TestCase):
    """An inner session's teardown must restore the outer session."""

    def setUp(self):
        self.campus, self.patch_token = make_api()

    def test_inner_teardown_preserves_outer_bearer(self):
        outer = self.patch_token("outer")
        with outer, self.campus.with_user_session(refresh_on_401=False):
            self.assertEqual(
                self.campus.api.client.authorization, "Bearer tok-outer")
            with (self.patch_token("inner"),
                  self.campus.with_user_session(refresh_on_401=False)):
                self.assertEqual(
                    self.campus.api.client.authorization,
                    "Bearer tok-inner")
            # The inner teardown used to reset the shared clients to
            # app Basic credentials here (#159) instead of restoring
            # the outer bearer.
            self.assertEqual(
                self.campus.api.client.authorization, "Bearer tok-outer")

    def test_inner_teardown_restores_outer_refresh_hook(self):
        def hook_of(client):
            # _unauthorized_hook is a CampusRequest attribute; the
            # clients are typed as the JsonClient ABC.
            return getattr(client, "_unauthorized_hook", None)

        with self.patch_token("outer"):
            with self.campus.with_user_session():  # refresh_on_401 default
                hook = hook_of(self.campus.api.client)
                self.assertIsNotNone(hook)
                with (self.patch_token("inner"),
                      self.campus.with_user_session(refresh_on_401=False)):
                    pass
                    # The inner teardown used to clear the outer hook.
                    self.assertIs(hook_of(self.campus.api.client), hook)
            self.assertIsNone(hook_of(self.campus.api.client))

    def test_top_level_teardown_restores_entry_authorization(self):
        # Device mode: no authorization at entry → teardown revokes
        # (reset_authorization sets env Basic; env creds are set in
        # this module for the client construction path).
        with (self.patch_token("inner"),
              self.campus.with_user_session(refresh_on_401=False)):
            pass
        auth = self.campus.api.client.authorization
        assert auth is not None  # narrowing for the type checker
        self.assertTrue(auth.startswith("Basic "))

    def test_top_level_teardown_restores_prior_bearer(self):
        self.campus.api.client.set_bearer_authorization("tok-prior")
        self.campus.auth.client.set_bearer_authorization("tok-prior")
        with self.patch_token("inner"):
            with self.campus.with_user_session(refresh_on_401=False):
                self.assertEqual(
                    self.campus.api.client.authorization, "Bearer tok-inner")
            self.assertEqual(
                self.campus.api.client.authorization, "Bearer tok-prior")
            self.assertEqual(
                self.campus.auth.client.authorization, "Bearer tok-prior")


if __name__ == "__main__":
    unittest.main()
