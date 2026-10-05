"""Tests for campus trace-context propagation on SDK calls (#92).

When the host app is traced (campus.audit.middleware.init_app), the
middleware stashes trace_id/span_id on flask.g for each request. SDK
sessions must attach those as X-Request-ID / X-Parent-Span-ID so the
receiving campus service records the call as a child span — and attach
nothing when there is no active traced request.
"""

import unittest

import flask
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

    def fake_send(prepared: requests.PreparedRequest, **_kwargs):
        captured["headers"] = dict(prepared.headers)
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response._content = b"{}"
        return response

    client._session.send = fake_send
    return captured


class TestTracePropagation(unittest.TestCase):
    """Trace headers on outbound SDK calls (#92)."""

    def test_headers_inside_traced_request(self):
        """Calls inside a traced host request carry both trace headers."""
        app = flask.Flask(__name__)
        client = _make_client()
        captured = _capture_send(client)

        with app.test_request_context("/"):
            flask.g.trace_id = TRACE_ID
            flask.g.span_id = SPAN_ID
            client.get("/ping")

        self.assertEqual(captured["headers"].get("X-Request-ID"), TRACE_ID)
        self.assertEqual(
            captured["headers"].get("X-Parent-Span-ID"), SPAN_ID
        )

    def test_no_headers_outside_request_context(self):
        """Calls outside any request context stay unparented."""
        client = _make_client()
        captured = _capture_send(client)

        client.get("/ping")

        self.assertNotIn("X-Request-ID", captured["headers"])
        self.assertNotIn("X-Parent-Span-ID", captured["headers"])

    def test_no_headers_without_active_span(self):
        """A request context without middleware-stashed span state
        (tracing disabled or middleware absent) emits no headers."""
        app = flask.Flask(__name__)
        client = _make_client()
        captured = _capture_send(client)

        with app.test_request_context("/"):
            client.get("/ping")

        self.assertNotIn("X-Request-ID", captured["headers"])
        self.assertNotIn("X-Parent-Span-ID", captured["headers"])

    def test_caller_headers_take_precedence(self):
        """Explicit per-call headers are never overwritten."""
        app = flask.Flask(__name__)
        client = _make_client()
        captured = _capture_send(client)

        with app.test_request_context("/"):
            flask.g.trace_id = TRACE_ID
            flask.g.span_id = SPAN_ID
            client._session.request(
                "GET",
                "http://testsuite.invalid/ping",
                headers={"X-Request-ID": "custom-trace-id"},
            )

        self.assertEqual(captured["headers"].get("X-Request-ID"), "custom-trace-id")
        self.assertEqual(
            captured["headers"].get("X-Parent-Span-ID"), SPAN_ID
        )

    def test_instrumentation_is_idempotent(self):
        """Sessions are instrumented at construction (#92); re-instrumenting
        (e.g. campus.api's init_app path) must be a no-op, not a second wrap."""
        client = _make_client()

        # Already instrumented at CampusRequest construction.
        self.assertFalse(
            tracing.instrument_requests_session(client._session)
        )

        # Still exactly one wrap: the header logic runs once per call.
        app = flask.Flask(__name__)
        captured = _capture_send(client)
        with app.test_request_context("/"):
            flask.g.trace_id = TRACE_ID
            flask.g.span_id = SPAN_ID
            client.get("/ping")

        self.assertEqual(captured["headers"].get("X-Request-ID"), TRACE_ID)


class TestJourneyForwarding(unittest.TestCase):
    """Action-journey forwarding on SDK calls (campus#828).

    When the host request carries an action journey (stashed as
    flask.g.journey_id by the journeys middleware), SDK calls forward it
    as X-Journey-ID so child services' spans join the same journey.
    """

    def test_journey_forwarded_inside_traced_request(self):
        app = flask.Flask(__name__)
        client = _make_client()
        captured = _capture_send(client)

        with app.test_request_context("/"):
            flask.g.trace_id = TRACE_ID
            flask.g.span_id = SPAN_ID
            flask.g.journey_id = "uid-journey-abc123"
            client.get("/ping")

        self.assertEqual(
            captured["headers"].get("X-Journey-ID"), "uid-journey-abc123"
        )
        self.assertEqual(captured["headers"].get("X-Request-ID"), TRACE_ID)

    def test_no_journey_no_header(self):
        """A traced request without a journey emits no journey header."""
        app = flask.Flask(__name__)
        client = _make_client()
        captured = _capture_send(client)

        with app.test_request_context("/"):
            flask.g.trace_id = TRACE_ID
            flask.g.span_id = SPAN_ID
            client.get("/ping")

        self.assertNotIn("X-Journey-ID", captured["headers"])

    def test_journey_header_outside_trace_context(self):
        """A journey without an active span still forwards (the journeys
        middleware can adopt journeys on hosts where span tracing is off;
        the trace headers are simply absent)."""
        app = flask.Flask(__name__)
        client = _make_client()
        captured = _capture_send(client)

        with app.test_request_context("/"):
            flask.g.journey_id = "uid-journey-abc123"
            client.get("/ping")

        self.assertEqual(
            captured["headers"].get("X-Journey-ID"), "uid-journey-abc123"
        )
        self.assertNotIn("X-Request-ID", captured["headers"])


if __name__ == "__main__":
    unittest.main()
