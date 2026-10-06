"""Unit tests for the audit ingest circuit breaker (#831).

Verifies trip/check semantics (floor, backoff, cap), two-stage
retraction (cooldown expiry opens the gate, 2xx clears), availability
error neutrality, fallback-key learning, and the observe hook on
Traces.ingest.
"""

import unittest
from unittest.mock import Mock

from campus_python.audit import ratelimit
from campus_python.audit.v1.traces import Traces


def _make_breaker() -> ratelimit.AuditRateBreaker:
    """A fresh breaker with backoff policy intact."""
    return ratelimit.AuditRateBreaker()


class TestBucketKey(unittest.TestCase):
    """Encoder mirrors the server-side priority order."""

    def test_pair(self):
        self.assertEqual(
            ratelimit.bucket_key("c1", "u1"), "client=c1;user=u1"
        )

    def test_user_only(self):
        self.assertEqual(ratelimit.bucket_key(None, "u1"), "user=u1")

    def test_client_only(self):
        self.assertEqual(ratelimit.bucket_key("c1", None), "client=c1")

    def test_identityless_is_wildcard(self):
        self.assertEqual(ratelimit.bucket_key(None, None), ratelimit.WILDCARD)


class TestObserve(unittest.TestCase):
    """observe() feeds 429s into trips, 2xx clears, others neutral."""

    def setUp(self):
        self.br = _make_breaker()

    def test_429_trips_with_retry_after(self):
        self.br.observe(429, {"Retry-After": "45"}, _body("user=u1"))
        retry_after = self.br.check("user=u1")
        self.assertIsNotNone(retry_after)
        self.assertGreaterEqual(retry_after, 44)
        self.assertLessEqual(retry_after, 46)

    def test_429_floor_30s(self):
        # Missing/invalid Retry-After falls back to the 30s floor.
        self.br.observe(429, None, _body("user=u1"))
        retry_after = self.br.check("user=u1")
        self.assertIsNotNone(retry_after)
        self.assertGreaterEqual(retry_after, 29)

    def test_429_without_bucket_trips_wildcard(self):
        self.br.observe(429, {"Retry-After": "30"}, {"error": {}})
        self.assertIsNotNone(self.br.check(ratelimit.WILDCARD))

    def test_availability_errors_are_neutral(self):
        for status in (500, 502, 503):
            self.br.observe(status, None, None)
        self.assertIsNone(self.br.check(ratelimit.WILDCARD))

    def test_2xx_clears_expired_trip(self):
        self.br.observe(429, {"Retry-After": "1"}, _body("user=u1"))
        # Simulate cooldown expiry without sleeping.
        self._expire("user=u1")
        # Gate is open (verifying state)...
        self.assertIsNone(self.br.check("user=u1"))
        # ...and the first 2xx ingest fully clears it.
        self.br.observe(201, None, None)
        self.assertIsNone(self.br.check("user=u1"))
        self.assertEqual(self.br._tripped, {})

    def test_2xx_does_not_clear_active_trip(self):
        self.br.observe(429, {"Retry-After": "120"}, _body("user=u1"))
        self.br.observe(201, None, None)
        self.assertIsNotNone(self.br.check("user=u1"))

    def test_consecutive_429s_back_off(self):
        self.br.observe(429, {"Retry-After": "1"}, _body("user=u1"))
        self._expire("user=u1")
        first_until = self.br._tripped["user=u1"]["until"]
        # Re-trip while verifying: backoff doubles (floor 30 -> 60).
        self.br.observe(429, {"Retry-After": "1"}, _body("user=u1"))
        second_until = self.br._tripped["user=u1"]["until"]
        now_gap = second_until - first_until
        self.assertGreater(now_gap, 0)

    def test_apikey_trip_learns_fallback(self):
        self.br.observe(429, {"Retry-After": "30"}, _body("apikey=k-123"))
        self.assertEqual(self.br.learned_fallback_key(), "apikey=k-123")

    def test_identity_trip_does_not_learn_fallback(self):
        self.br.observe(429, {"Retry-After": "30"}, _body("client=c1;user=u1"))
        self.assertIsNone(self.br.learned_fallback_key())

    def _expire(self, key: str) -> None:
        """Force a trip's cooldown into the past (verifying state)."""
        self.br._tripped[key]["until"] -= 10_000


def _body(bucket: str) -> dict:
    """A 429 error envelope as emitted by campus.audit (#835)."""
    return {"error": {"code": "RATE_LIMITED", "details": {"bucket": bucket}}}


class TestCheckRequest(unittest.TestCase):
    """Gate checks: per-identity when resolvable, coarse otherwise."""

    def setUp(self):
        self.br = _make_breaker()

    def test_identity_check_matches_encoded_bucket(self):
        self.br.observe(429, {"Retry-After": "30"}, _body("client=c1;user=u1"))
        self.assertIsNotNone(self.br.check_request(client_id="c1", user_id="u1"))
        self.assertIsNone(self.br.check_request(client_id="c1", user_id="other"))
        self.assertIsNone(self.br.check_request(client_id="other", user_id="u1"))

    def test_identityless_uses_learned_fallback(self):
        self.br.observe(429, {"Retry-After": "30"}, _body("apikey=k-123"))
        self.assertIsNotNone(self.br.check_request())

    def test_identityless_without_learning_uses_wildcard(self):
        self.br.observe(429, {"Retry-After": "30"}, _body(ratelimit.WILDCARD))
        self.assertIsNotNone(self.br.check_request())

    def test_untripped_identity_is_open(self):
        self.assertIsNone(self.br.check_request(client_id="c1", user_id="u1"))


class TestIngestHook(unittest.TestCase):
    """Traces.ingest feeds the module breaker before raising."""

    def setUp(self):
        ratelimit.breaker.reset()
        self.addCleanup(ratelimit.breaker.reset)

    def _ingest_with_response(self, status: int, body: dict, raises: bool):
        resp = Mock()
        resp.status_code = status
        resp.headers = {"Retry-After": "30"}
        resp.json.return_value = body
        if raises:
            resp.raise_for_status.side_effect = RuntimeError(f"{status}")
        client = Mock()
        client.post.return_value = resp
        traces = Traces(client=client, root=Mock())
        return traces

    def test_429_ingest_trips_breaker_and_raises(self):
        traces = self._ingest_with_response(
            429, _body("client=c1;user=u1"), raises=True
        )
        with self.assertRaises(RuntimeError):
            traces.ingest([{"span_id": "s1"}])
        self.assertIsNotNone(
            ratelimit.breaker.check_request(client_id="c1", user_id="u1")
        )

    def test_201_ingest_does_not_trip(self):
        traces = self._ingest_with_response(201, {"created": ["s1"]}, raises=False)
        traces.ingest([{"span_id": "s1"}])
        self.assertEqual(ratelimit.breaker._tripped, {})


if __name__ == "__main__":
    unittest.main()
