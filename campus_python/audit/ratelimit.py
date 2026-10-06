"""campus_python.audit.ratelimit

Circuit breaker for campus.audit ingest rate limiting.

Phase 3 of the audit API key security epic (campus#538), tracked in
campus#831. Design:
https://github.com/nyjc-computing/campus/issues/538#issuecomment-5996377544

How it fits together:

- campus.audit rate-limits POST /traces/ per identity with a per-minute
  token bucket and returns 429 with a Retry-After header and the
  tripped bucket key in error.details.bucket.
- The producers' ingest responses are fed to the module-level `breaker`
  (see Traces.ingest here, and campus.audit.client's Traces.new — the
  two clients that POST spans). A 429 trips the bucket; a 2xx clears
  trips whose cooldown has expired; any other outcome (timeout,
  connection refused, 5xx) is neutral — an audit outage must not take
  producers down.
- Producers consult `breaker.check_request(...)` at request entry
  (flag-gated on their side via AUDIT_TRACING_FAIL_CLOSED) and
  short-circuit matching requests with 503 + Retry-After while a
  bucket is tripped.

State is per worker process (the module singleton). Cross-worker
staleness means the limit is not strictly adhered to — ratified slack.
Retraction is two-stage: cooldown expiry OPENS the gate (verifying)
without clearing the trip; the first 2xx ingest clears it; another 429
re-trips with exponential backoff (floor 30s, x2, cap 5 min).
"""

__all__ = [
    "AuditRateBreaker",
    "WILDCARD",
    "breaker",
    "bucket_key",
]

import threading
import time
import typing

# Bucket key for requests whose identity (or learned fallback bucket)
# is unknown; producers gate these coarsely.
WILDCARD = "*"

# Backoff policy: floor 30s, x2 per consecutive trip for the same
# bucket, capped at 5 minutes. Audit's Retry-After is honored up to
# the same cap (its per-minute bucket never advises more than 60s).
BACKOFF_FLOOR_SECONDS = 30.0
BACKOFF_CAP_SECONDS = 300.0


def bucket_key(client_id: str | None, user_id: str | None) -> str:
    """Encode a request's identity into a rate-limit bucket key.

    Mirrors the server-side encoder (campus.audit.resources.ratelimit):
    (client_id, user_id) pair > user_id > client_id. An identity-less
    request maps to the wildcard sentinel — the server keys those
    spans by the producer's API key, which the producer learns from
    429 bodies (see AuditRateBreaker.learned_fallback_key).
    """
    if client_id and user_id:
        return f"client={client_id};user={user_id}"
    if user_id:
        return f"user={user_id}"
    if client_id:
        return f"client={client_id}"
    return WILDCARD


class AuditRateBreaker:
    """Thread-safe in-process circuit breaker for audit ingest 429s."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # bucket key -> {"until": epoch seconds, "consecutive": int}
        self._tripped: dict[str, dict[str, float]] = {}
        # Learned producer-key fallback bucket ("apikey=..."), from
        # 429 bodies. An apikey= bucket seen by this process's client
        # is necessarily this producer's own fallback bucket.
        self._fallback_key: str | None = None

    def observe(
            self,
            status_code: int,
            headers: typing.Mapping[str, str] | None = None,
            body: typing.Any = None,
    ) -> None:
        """Feed an ingest response to the breaker.

        2xx clears trips whose cooldown has expired (verifying state);
        429 trips the bucket named in the body (or the wildcard when
        the body carries no bucket key); anything else — timeouts,
        connection errors, 5xx — is neutral (the ratified split:
        availability errors neither set nor clear).
        """
        if 200 <= status_code < 300:
            self._clear_expired()
            return
        if status_code != 429:
            return

        bucket = _bucket_from_body(body) or WILDCARD
        retry_after = _retry_after_seconds(headers)
        self.trip(bucket, retry_after)
        if bucket.startswith("apikey="):
            with self._lock:
                self._fallback_key = bucket

    def trip(self, bucket_key: str, retry_after: float) -> None:
        """Trip (or re-trip) a bucket with backoff on consecutive trips.

        Trip duration = min(cap, max(Retry-After, floor * 2**(n-1)))
        where n counts consecutive trips of this bucket without an
        intervening successful ingest.
        """
        now = time.time()
        with self._lock:
            previous = self._tripped.get(bucket_key)
            consecutive = int(previous["consecutive"]) + 1 if previous else 1
            backoff = min(
                BACKOFF_FLOOR_SECONDS * 2 ** (consecutive - 1),
                BACKOFF_CAP_SECONDS,
            )
            duration = min(BACKOFF_CAP_SECONDS, max(retry_after, backoff))
            self._tripped[bucket_key] = {
                "until": now + duration,
                "consecutive": consecutive,
            }

    def check(self, bucket_key: str) -> int | None:
        """Return seconds until the bucket reopens, or None if open.

        A trip whose cooldown has expired is in the verifying state:
        the gate is open (None) and only a 2xx or another 429 resolves
        it (see observe).
        """
        now = time.time()
        with self._lock:
            trip = self._tripped.get(bucket_key)
            if trip is not None and now < trip["until"]:
                return int(trip["until"] - now) + 1
            return None

    def check_request(
            self,
            client_id: str | None = None,
            user_id: str | None = None,
    ) -> int | None:
        """Gate check for one incoming request.

        Per-identity when the request's identity is resolvable at
        entry; otherwise the learned producer-key fallback bucket, or
        the wildcard when nothing has been learned yet.
        """
        if client_id or user_id:
            return self.check(bucket_key(client_id, user_id))
        fallback = self.learned_fallback_key()
        if fallback is not None:
            return self.check(fallback)
        return self.check(WILDCARD)

    def learned_fallback_key(self) -> str | None:
        """The producer's own apikey= bucket key, learned from 429s."""
        with self._lock:
            return self._fallback_key

    def reset(self) -> None:
        """Clear all state (tests)."""
        with self._lock:
            self._tripped.clear()
            self._fallback_key = None

    def _clear_expired(self) -> None:
        """Drop trips whose cooldown has expired (successful ingest)."""
        now = time.time()
        with self._lock:
            expired = [
                key for key, trip in self._tripped.items()
                if now >= trip["until"]
            ]
            for key in expired:
                del self._tripped[key]


def _bucket_from_body(body: typing.Any) -> str | None:
    """Extract the tripped bucket key from a 429 error envelope.

    Shape (campus.audit #835): {"error": {"details": {"bucket": ...}}}.
    Returns None when absent or malformed.
    """
    try:
        bucket = body["error"]["details"]["bucket"]
    except (KeyError, TypeError, IndexError):
        return None
    return bucket if isinstance(bucket, str) and bucket else None


def _retry_after_seconds(headers: typing.Mapping[str, str] | None) -> float:
    """Parse Retry-After from response headers, defaulting to the floor."""
    if headers:
        try:
            return float(headers.get("Retry-After"))
        except (TypeError, ValueError):
            pass
    return BACKOFF_FLOOR_SECONDS


# Per-process singleton: all ingest responses in this worker feed it,
# and every gate check consults it.
breaker = AuditRateBreaker()
