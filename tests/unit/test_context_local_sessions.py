"""Concurrent sessions on a shared Campus must not leak credentials (#189).

The classroom prod incident (2026-11-25, classroom#153): a gthread Flask
host drives ONE Campus from 2×8 request threads. The old implementation
mutated the shared session headers inside with_user_session(), so a
thread inside a session block left its USER bearer where an interleaving
thread's ambient call (flask_campus's push_context resolution) presented
it — campus.auth denies user principals on session-flow routes
(#854/#1055) and the request degraded to anonymous, looping the browser
into /login. These tests pin the context-local contract.
"""

import base64
import json
import os
import threading
import unittest
from typing import cast
from unittest import mock
from unittest.mock import MagicMock, Mock

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
    raw.headers["Content-Type"] = "application/json"
    return raw


def make_client() -> CampusRequest:
    client = CampusRequest(base_url="https://api.example.test", mode="server")
    client._session = MagicMock()
    client._session.headers = {}
    # Server-mode ambient state, as a real client would carry.
    client.reset_authorization()
    return client


def make_campus() -> tuple[Campus, CampusRequest]:
    """A Campus whose auth/api roots share one recording client."""
    campus = Campus.__new__(Campus)
    campus._mode = "server"
    client = make_client()
    campus._auth = mock.Mock(client=client)
    campus._api = mock.Mock(client=client)
    return campus, client


class TestConcurrentSessions(unittest.TestCase):
    """The #189 contract on a shared instance under thread interleaving."""

    def setUp(self):
        self.campus, self.client = make_campus()
        self.get_token = mock.patch.object(
            Campus, "_get_token_from_session",
            return_value=Mock(access_token="user-token"),
        ).start()
        self.addCleanup(mock.patch.stopall)

    def recorded_calls(self) -> list[tuple[str, str | None]]:
        """(url, Authorization) for every request the client sent."""
        calls = cast(MagicMock, self.client._session).request.call_args_list
        out = []
        for call in calls:
            url = call.args[1] if len(call.args) > 1 else call.kwargs.get("url", "")
            headers = call.kwargs.get("headers") or {}
            out.append(
                (
                    url,
                    headers.get(
                        "Authorization",
                        self.client._session.headers.get("Authorization"),
                    ),
                )
            )
        return out

    def test_ambient_call_stays_client_credential_during_session(self):
        """An ambient (no session) call made while another context holds
        a user session carries Basic client credentials, never the
        session's bearer."""
        in_session = threading.Event()
        ambient_done = threading.Event()

        def ambient_thread():
            # Wait until the other thread is INSIDE its session block.
            in_session.wait(timeout=5)
            self.campus.api.client.get("/ambient")
            ambient_done.set()

        worker = threading.Thread(target=ambient_thread)
        worker.start()
        with self.campus.with_user_session():
            in_session.set()
            ambient_done.wait(timeout=5)
            self.campus.api.client.get("/in-session")

        worker.join(timeout=5)
        headers = [auth for _, auth in self.recorded_calls()]
        self.assertEqual(len(headers), 2)
        self.assertEqual(headers[0], BASIC_AUTH)
        self.assertEqual(headers[1], "Bearer user-token")

    def test_session_teardown_restores_ambient_state(self):
        """After the block, ambient calls go out with client credentials."""
        with self.campus.with_user_session():
            self.campus.api.client.get("/in-session")
        self.campus.api.client.get("/after")

        headers = [auth for _, auth in self.recorded_calls()]
        self.assertEqual(headers[0], "Bearer user-token")
        self.assertTrue(headers[1].startswith("Basic "))

    def test_nested_app_session_restores_user_bearer(self):
        """An inner with_app_session inside with_user_session: the inner
        block carries the app bearer, and the outer user bearer resumes
        after it (#159 semantics, now override-based)."""
        self.campus._auth.token.return_value = mock.Mock(access_token="app-token")
        with self.campus.with_user_session():
            self.campus.api.client.get("/outer-1")
            with self.campus.with_app_session():
                self.campus.api.client.get("/inner")
            self.campus.api.client.get("/outer-2")

        calls = {url.rsplit("/", 1)[-1]: auth for url, auth in self.recorded_calls()}
        self.assertEqual(calls["outer-1"], "Bearer user-token")
        self.assertEqual(calls["inner"], "Bearer app-token")
        self.assertEqual(calls["outer-2"], "Bearer user-token")

    def test_stress_interleaved_sessions_and_ambient_calls(self):
        """Hammer the invariant: across many interleaved threads, every
        in-session request carries the session bearer and every ambient
        request carries Basic — no cross-talk in either direction."""
        errors_seen: list[str] = []
        lock = threading.Lock()

        def session_worker():
            for _ in range(50):
                with self.campus.with_user_session():
                    self.campus.api.client.get("/s")
                    self.campus.api.client.get("/s")

        def ambient_worker():
            for _ in range(100):
                self.campus.api.client.get("/a")

        def tracked(target):
            def run():
                try:
                    target()
                except Exception as exc:  # pragma: no cover — failure path
                    with lock:
                        errors_seen.append(repr(exc))
            return run

        threads = (
            [threading.Thread(target=tracked(session_worker)) for _ in range(4)]
            + [threading.Thread(target=tracked(ambient_worker)) for _ in range(4)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(errors_seen, [])
        calls = self.recorded_calls()
        for url, auth in calls:
            if url.endswith("/s"):
                self.assertEqual(auth, "Bearer user-token", url)
            else:
                self.assertEqual(auth, BASIC_AUTH, url)


if __name__ == "__main__":
    unittest.main()
