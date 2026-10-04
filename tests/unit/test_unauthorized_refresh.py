"""Tests for the 401 auto-refresh hook (issue #89).

CampusRequest.set_unauthorized_hook() installs a one-shot refresh hook:
on a 401 response the hook runs once, and if it returns a bearer token
the Authorization header is refreshed and the request retried once.
Failures (hook returns None, or the retry 401s again) surface the
original 401 to the caller — the hook is strictly a safety net.

Campus.with_user_session(refresh_on_401=True) wires the hook so the
refresh round-trip force-refreshes the session token, authenticating as
the client (Basic) like session establishment does.
"""

import json
import os
import unittest
from unittest import mock
from unittest.mock import MagicMock, Mock

import requests

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")

from campus_python import Campus, errors
from campus_python.json_client import CampusRequest


def raw_response(status_code: int, payload: dict | None = None) -> requests.Response:
    """Build a real requests.Response so CampusResponse parses it."""
    raw = requests.Response()
    raw.status_code = status_code
    raw._content = json.dumps(payload or {}).encode("utf-8")
    raw.headers["Content-Type"] = "application/json"
    return raw


def make_client() -> CampusRequest:
    client = CampusRequest(base_url="https://api.example.test", mode="device")
    client._session = MagicMock()
    # A real dict: set_bearer_authorization writes headers["..."] and
    # the tests read it back
    client._session.headers = {}
    return client


class TestUnauthorizedHook(unittest.TestCase):
    """set_unauthorized_hook(): retry-once semantics on 401."""

    def setUp(self):
        self.client = make_client()

    def set_responses(self, *responses: requests.Response) -> MagicMock:
        self.client._session.request.side_effect = list(responses)
        return self.client._session.request

    def test_401_triggers_hook_and_retries(self):
        request_mock = self.set_responses(
            raw_response(401, {"error": {"code": "AUTH_TOKEN_INVALID"}}),
            raw_response(200, {"ok": True}),
        )
        self.client.set_unauthorized_hook(lambda: "fresh-token")

        resp = self.client.get("/things")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(request_mock.call_count, 2)
        self.assertEqual(
            self.client._session.headers["Authorization"], "Bearer fresh-token"
        )

    def test_hook_returning_none_keeps_original_401(self):
        request_mock = self.set_responses(raw_response(401, {}))
        self.client.set_unauthorized_hook(lambda: None)

        resp = self.client.get("/things")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(request_mock.call_count, 1)
        self.assertNotIn("Authorization", self.client._session.headers)

    def test_no_hook_401_passes_through(self):
        request_mock = self.set_responses(raw_response(401, {}))

        resp = self.client.get("/things")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(request_mock.call_count, 1)

    def test_second_401_not_retried_again(self):
        request_mock = self.set_responses(
            raw_response(401, {}), raw_response(401, {})
        )
        calls: list[int] = []
        self.client.set_unauthorized_hook(lambda: calls.append(1) or "tok")

        resp = self.client.get("/things")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(len(calls), 1)
        self.assertEqual(request_mock.call_count, 2)

    def test_reentrant_hook_call_skips_hook(self):
        """Requests made from inside the hook skip the hook — a hook
        that calls back into this client cannot recurse."""
        request_mock = self.set_responses(
            raw_response(401, {}),   # outer request
            raw_response(401, {}),   # hook's own inner request
            raw_response(401, {}),   # outer retry
        )

        def hook() -> str:
            inner = self.client.get("/inner")
            self.assertEqual(inner.status_code, 401)
            return "tok"

        self.client.set_unauthorized_hook(hook)
        resp = self.client.get("/outer")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(request_mock.call_count, 3)

    def test_clearing_hook_disables_retry(self):
        request_mock = self.set_responses(raw_response(401, {}))
        self.client.set_unauthorized_hook(lambda: "tok")
        self.client.set_unauthorized_hook(None)

        resp = self.client.get("/things")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(request_mock.call_count, 1)

    def test_post_retries_like_get(self):
        request_mock = self.set_responses(
            raw_response(401, {}), raw_response(200, {"id": "x1"})
        )
        self.client.set_unauthorized_hook(lambda: "fresh-token")

        resp = self.client.post("/things", json={"k": "v"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(request_mock.call_count, 2)
        # The retry replays the same body
        self.assertEqual(request_mock.call_args.kwargs["json"], {"k": "v"})


class TestWithUserSessionWiring(unittest.TestCase):
    """with_user_session() installs a force-refresh hook on both
    service clients and removes it when the session closes."""

    def setUp(self):
        self.campus = Campus.__new__(Campus)
        self.campus._mode = "server"

        self.api_client = make_client()
        self.auth_client = make_client()
        self.api_root = Mock(client=self.api_client)
        self.auth_root = Mock(client=self.auth_client)

        patchers = [
            mock.patch.object(
                Campus, "api", new_callable=mock.PropertyMock,
                return_value=self.api_root,
            ),
            mock.patch.object(
                Campus, "auth", new_callable=mock.PropertyMock,
                return_value=self.auth_root,
            ),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.get_token = mock.patch.object(
            Campus, "_get_token_from_session"
        ).start()
        self.addCleanup(mock.patch.stopall)

        token1 = Mock(access_token="tok1")
        self.get_token.return_value = token1

    def test_401_mid_session_force_refreshes_and_retries(self):
        self.api_client._session.request.side_effect = [
            raw_response(401, {}), raw_response(200, {"ok": True}),
        ]
        token2 = Mock(access_token="tok2")
        self.get_token.side_effect = [Mock(access_token="tok1"), token2]

        with self.campus.with_user_session():
            resp = self.campus.api.client.get("/things")
            # The new bearer is live on BOTH service clients mid-session
            self.assertEqual(
                self.api_client._session.headers["Authorization"],
                "Bearer tok2",
            )
            self.assertEqual(
                self.auth_client._session.headers["Authorization"],
                "Bearer tok2",
            )

        self.assertEqual(resp.status_code, 200)
        # Second call is the hook's force-refresh
        self.assertEqual(self.get_token.call_count, 2)
        self.assertTrue(self.get_token.call_args.kwargs["force_refresh"])

    def test_refresh_failure_surfaces_original_401(self):
        self.api_client._session.request.side_effect = [raw_response(401, {})]
        self.get_token.side_effect = [
            Mock(access_token="tok1"),
            errors.AuthenticationError(error_description="session gone"),
        ]

        with self.campus.with_user_session():
            resp = self.campus.api.client.get("/things")
            # Pre-hook bearer state restored after the failed refresh
            self.assertEqual(
                self.api_client._session.headers["Authorization"],
                "Bearer tok1",
            )

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self.api_client._session.request.call_count, 1)

    def test_hooks_cleared_after_session(self):
        with self.campus.with_user_session():
            self.assertIsNotNone(self.api_client._unauthorized_hook)
            self.assertIsNotNone(self.auth_client._unauthorized_hook)

        self.assertIsNone(self.api_client._unauthorized_hook)
        self.assertIsNone(self.auth_client._unauthorized_hook)

    def test_refresh_on_401_false_keeps_old_behaviour(self):
        self.api_client._session.request.side_effect = [raw_response(401, {})]

        with self.campus.with_user_session(refresh_on_401=False):
            self.assertIsNone(self.api_client._unauthorized_hook)
            resp = self.campus.api.client.get("/things")

        self.assertEqual(resp.status_code, 401)
        self.get_token.assert_called_once()  # only the proactive refresh


if __name__ == "__main__":
    unittest.main()
