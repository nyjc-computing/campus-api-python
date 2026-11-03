"""Tests for campus trace-context propagation on SDK calls (#92).

When the host app is traced (campus.audit.middleware.init_app), the
middleware stashes trace_id/span_id on flask.g for each request. SDK
sessions must attach those as X-Request-ID / X-Parent-Span-ID so the
receiving campus service records the call as a child span — and attach
nothing when there is no active traced request.
"""

import os
import unittest

import requests

from campus_python import tracing
from campus_python.json_client import CampusRequest

TRACE_ID = "a" * 32
SPAN_ID = "b" * 16


def _make_client() -> CampusRequest:
    """Build an unauthenticated client against a dummy base URL."""
    return CampusRequest(base_url="http://testsuite.invalid", mode="device")


def _capture_send(client: CampusRequest) -> dict:
    """Replace the session transport with a capture stub.

    Returns a dict that receives the outgoing request's headers.
    """
    captured: dict = {}

    def fake_send(request: requests.PreparedRequest, **_kwargs):
        captured["headers"] = dict(request.headers)
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response._content = b"{}"
        return response

    client._session.send = fake_send
    return captured


class TestTracePropagation(unittest.TestCase):
    """Trace headers on outbound SDK calls (#92)."""

    def test_no_headers_outside_request_context(self):
        """Calls outside any request context stay unparented."""
        client = _make_client()
        captured = _capture_send(client)

        client.get("/ping")

        self.assertNotIn("X-Request-ID", captured["headers"])
        self.assertNotIn("X-Parent-Span-ID", captured["headers"])

    def test_instrumentation_is_idempotent(self):
        """Sessions are instrumented at construction (#92); re-instrumenting
        (e.g. campus.api's init_app path) must be a no-op, not a second wrap."""
        client = _make_client()

        # Already instrumented at CampusRequest construction.
        self.assertFalse(
            tracing.instrument_requests_session(client._session)
        )

        # Still exactly one wrap: the header logic runs once per call
        # (headers sourced from the installed request-context provider).
        tracing.set_request_context_provider(
            lambda: {"X-Request-ID": TRACE_ID}
        )
        self.addCleanup(tracing.set_request_context_provider, None)
        captured = _capture_send(client)
        client.get("/ping")

        self.assertEqual(captured["headers"].get("X-Request-ID"), TRACE_ID)


class TestJourneyNameForwarding(unittest.TestCase):
    """Journey-label forwarding on SDK calls (campus#952).

    When the host stashes a journey name (flask.g.journey_name — set by
    flask_campus's @journey decorator or by the journeys middleware
    adopting X-Journey-Name), SDK calls forward it alongside the id so
    child services' spans tag the same journey_name.
    """

    def test_name_lockstep_with_campus_middleware(self):
        """The header name must match the campus journeys middleware's
        adoption constant — the two modules carry keep-in-lockstep
        notes and the whole chain breaks silently if they drift."""
        self.assertEqual(tracing.JOURNEY_NAME_HEADER, "X-Journey-Name")


class TestProcessJourney(unittest.TestCase):
    """Boot journey + process device on out-of-request calls (#114).

    Ruling (2026-10-21): every SDK call is a user request — human or
    agent — so out-of-request calls (startup, background threads)
    correlate under one journey per process boot, attributed to the
    operator. Strict MVP: in-request calls never inherit the journey.
    """

    def setUp(self):
        tracing._reset_process_journey()
        self.addCleanup(tracing._reset_process_journey)
        # Snapshot and clear both env knobs so tests are deterministic
        # regardless of the host environment.
        self._saved_env = {
            key: os.environ.get(key)
            for key in (tracing.PROCESS_JOURNEY_ENV, tracing.PROCESS_DEVICE_ENV)
        }
        for key in self._saved_env:
            os.environ.pop(key, None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _client(self):
        client = _make_client()
        self.captured = _capture_send(client)
        return client

    def test_out_of_request_call_carries_boot_journey(self):
        client = self._client()

        client.get("/ping")

        journey_id = self.captured["headers"].get("X-Journey-ID")
        self.assertTrue(journey_id.startswith("uid-journey-"))
        # Auto-minted: no name until the app sets one.
        self.assertNotIn("X-Journey-Name", self.captured["headers"])

    def test_one_journey_per_process(self):
        """The minted id stays fixed across calls — one journey per boot."""
        client = self._client()

        client.get("/ping")
        first = self.captured["headers"].get("X-Journey-ID")
        client.get("/ping")

        self.assertEqual(self.captured["headers"].get("X-Journey-ID"), first)

    def test_explicit_id_and_name_via_api(self):
        tracing.set_process_journey("uid-journey-custom01", name="campus.api.boot")
        client = self._client()

        client.get("/ping")

        self.assertEqual(
            self.captured["headers"].get("X-Journey-ID"), "uid-journey-custom01"
        )
        self.assertEqual(
            self.captured["headers"].get("X-Journey-Name"), "campus.api.boot"
        )

    def test_set_process_journey_mints_and_returns_id(self):
        journey_id = tracing.set_process_journey(name="campus.yapper.boot")

        self.assertTrue(journey_id.startswith("uid-journey-"))
        client = self._client()
        client.get("/ping")
        self.assertEqual(self.captured["headers"].get("X-Journey-ID"), journey_id)
        self.assertEqual(
            self.captured["headers"].get("X-Journey-Name"), "campus.yapper.boot"
        )

    def test_env_opt_out_suppresses_journey(self):
        os.environ[tracing.PROCESS_JOURNEY_ENV] = "off"
        client = self._client()

        client.get("/ping")

        self.assertNotIn("X-Journey-ID", self.captured["headers"])
        self.assertNotIn("X-Journey-Name", self.captured["headers"])

    def test_disable_api_suppresses_journey(self):
        tracing.disable_process_journey()
        client = self._client()

        client.get("/ping")

        self.assertNotIn("X-Journey-ID", self.captured["headers"])

    def test_set_process_journey_reenables_after_disable(self):
        tracing.disable_process_journey()
        tracing.set_process_journey(name="campus.api.boot")
        client = self._client()

        client.get("/ping")

        self.assertTrue(self.captured["headers"].get("X-Journey-ID", "").startswith(
            "uid-journey-"
        ))

    def test_env_explicit_id_pinned(self):
        """A non-off CAMPUS_PROCESS_JOURNEY value pins that id (e.g. to
        correlate a known deploy) instead of auto-minting."""
        os.environ[tracing.PROCESS_JOURNEY_ENV] = "uid-journey-deploy42"
        client = self._client()

        client.get("/ping")

        self.assertEqual(
            self.captured["headers"].get("X-Journey-ID"), "uid-journey-deploy42"
        )

    def test_process_device_from_railway_env(self):
        os.environ[tracing.PROCESS_DEVICE_ENV] = "deploy-abc123"
        client = self._client()

        client.get("/ping")

        self.assertEqual(
            self.captured["headers"].get("X-Campus-Device"), "deploy-abc123"
        )

    def test_set_process_device_overrides_env(self):
        os.environ[tracing.PROCESS_DEVICE_ENV] = "deploy-abc123"
        tracing.set_process_device("deploy-xyz789")
        client = self._client()

        client.get("/ping")

        self.assertEqual(
            self.captured["headers"].get("X-Campus-Device"), "deploy-xyz789"
        )

    def test_minted_id_matches_campus_format(self):
        """uid-journey-<first 16 chars of the hyphenated uuid4>, matching
        campus.common.utils.uid.generate_category_uid("journey")."""
        journey_id = tracing._mint_journey_id()

        self.assertTrue(journey_id.startswith("uid-journey-"))
        suffix = journey_id.removeprefix("uid-journey-")
        self.assertEqual(len(suffix), 16)
        self.assertEqual(suffix.count("-"), 2)


class TestSetDefaultHeader(unittest.TestCase):
    """JsonClient.set_default_header for non-browser identity (#837)."""

    def test_default_header_sent_on_every_request(self):
        client = _make_client()
        captured = _capture_send(client)

        client.set_default_header("X-Campus-Device", "uid-device-cli42")
        client.get("/ping")

        self.assertEqual(
            captured["headers"].get("X-Campus-Device"), "uid-device-cli42"
        )

    def test_default_header_persists_across_calls(self):
        client = _make_client()
        captured = _capture_send(client)
        client.set_default_header("X-Campus-Device", "uid-device-cli42")

        client.get("/ping")
        client.get("/ping")

        self.assertEqual(
            captured["headers"].get("X-Campus-Device"), "uid-device-cli42"
        )


if __name__ == "__main__":
    unittest.main()
