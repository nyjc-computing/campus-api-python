"""Nested with_user_session must preserve the outer session (#159).

The auth-broker release runs a with_user_session inside a route that
already holds one (campus-classroom's enrollment bridge): the inner
teardown must restore the outer session's credential, not drop the
block back to app Basic credentials mid-outer-session.

Since #189 both the bearer and the 401 hook are context-local: the
override is saved/restored per block, the shared session headers are
never touched, and ambient calls always carry the instance credential.
These tests pin that contract via the Authorization header each request
actually carried (a recording MagicMock session — no network).
"""

import base64
import json
import os
import unittest
from types import SimpleNamespace
from typing import cast
from unittest import mock
from unittest.mock import MagicMock

import requests

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")

from campus_python import Campus
from campus_python.json_client import CampusRequest

BASIC_AUTH = "Basic " + base64.b64encode(
    b"test-client-id:test-client-secret"
).decode("ascii")


def raw_response(status_code: int, payload: dict | None = None) -> requests.Response:
    raw = requests.Response()
    raw.status_code = status_code
    raw._content = json.dumps(payload or {}).encode("utf-8")
    return raw


class TestNestedUserSessions(unittest.TestCase):
    """An inner session's teardown must restore the outer session."""

    def setUp(self):
        os.environ["CAMPUS_AUTH_URL"] = "http://localhost"
        os.environ["CAMPUS_API_URL"] = "http://localhost"
        self.campus = Campus(mode="server")
        client = CampusRequest(base_url="http://localhost", mode="server")
        client._session = MagicMock()
        client._session.headers = {}
        client.reset_authorization()
        self.client = client

        self.campus._auth = mock.Mock(client=client)
        self.campus._api = mock.Mock(client=client)
        def _ok_response(*_args, **_kwargs):
            return raw_response(200, {"ok": True})

        cast(MagicMock, client._session).request.side_effect = _ok_response

    def auth_for(self, path: str) -> str | None:
        calls = cast(MagicMock, self.client._session).request.call_args_list
        for call in calls:
            url = call.args[1] if len(call.args) > 1 else ""
            if url.endswith(path):
                headers = call.kwargs.get("headers") or {}
                return headers.get(
                    "Authorization", self.client._session.headers.get("Authorization")
                )
        return None

    def token_patch(self, name: str):
        """Patch the login-session mint (and the app-credentials mint)."""
        token = SimpleNamespace(access_token=f"tok-{name}")
        get_token = mock.patch.object(
            Campus, "_get_token_from_session", return_value=token,
        )
        app_token = mock.patch.object(
            self.campus._auth, "token", return_value=token,
        )
        return get_token, app_token

    def test_inner_teardown_preserves_outer_bearer(self):
        outer_get, outer_app = self.token_patch("outer")
        inner_get, inner_app = self.token_patch("inner")
        with outer_get, outer_app:
            with self.campus.with_user_session(refresh_on_401=False):
                self.campus.api.client.get("/outer")
                self.assertEqual(self.auth_for("/outer"), "Bearer tok-outer")
                with (inner_get, inner_app,
                      self.campus.with_user_session(refresh_on_401=False)):
                    self.campus.api.client.get("/inner")
                    self.assertEqual(
                        self.auth_for("/inner"), "Bearer tok-inner")
                # The inner teardown used to reset the shared clients to
                # app Basic credentials here (#159) instead of restoring
                # the outer bearer.
                self.campus.api.client.get("/after-inner")
                self.assertEqual(
                    self.auth_for("/after-inner"), "Bearer tok-outer")
            self.campus.api.client.get("/after-outer")
            self.assertEqual(self.auth_for("/after-outer"), BASIC_AUTH)

    def test_inner_teardown_restores_outer_refresh_hook(self):
        from campus_python.json_client import _session_hook

        get_token, app_token = self.token_patch("outer")
        with get_token, app_token:
            with self.campus.with_user_session():  # refresh_on_401 default
                hook = _session_hook.get()
                self.assertIsNotNone(hook)
                with self.campus.with_user_session(refresh_on_401=False):
                    # The inner (hookless) session must not clear the
                    # outer session's hook.
                    self.assertIs(_session_hook.get(), hook)
                self.assertIs(_session_hook.get(), hook)
            self.assertIsNone(_session_hook.get())

    def test_ambient_state_untouched_by_sessions(self):
        """Session blocks never mutate the shared session headers: the
        instance credential before, during and after a session is the
        app Basic credential; in-block requests carry the override."""
        get_token, app_token = self.token_patch("inner")
        with get_token, app_token:
            before = self.campus.api.client.authorization
            self.assertEqual(before, BASIC_AUTH)
            with self.campus.with_user_session(refresh_on_401=False):
                self.campus.api.client.get("/during")
                self.assertEqual(
                    self.campus.api.client.authorization, before)
            self.assertEqual(self.campus.api.client.authorization, before)
            self.assertEqual(self.auth_for("/during"), "Bearer tok-inner")

    def test_prior_instance_bearer_left_alone(self):
        """A bearer set on the instance by the host (legacy use_token
        callers) is not consumed or cleared by a session block; the
        block's requests use the session token, ambient requests keep
        the instance bearer."""
        self.campus.api.client.set_bearer_authorization("tok-prior")
        get_token, app_token = self.token_patch("inner")
        with get_token, app_token:
            with self.campus.with_user_session(refresh_on_401=False):
                self.campus.api.client.get("/during")
                self.assertEqual(self.auth_for("/during"), "Bearer tok-inner")
            self.assertEqual(
                self.campus.api.client.authorization, "Bearer tok-prior")
            self.campus.api.client.get("/after")
            self.assertEqual(self.auth_for("/after"), "Bearer tok-prior")


if __name__ == "__main__":
    unittest.main()
